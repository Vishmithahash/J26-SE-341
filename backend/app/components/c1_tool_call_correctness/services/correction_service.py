import os
import shutil
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.correction import (
    CandidatePatch,
    CorrectionAttemptRequest,
    CorrectionDiffResponse,
    CorrectionRecord,
    CorrectionStatus,
    CorrectionSummary,
    ReviewDecision,
    ReviewRecord,
    ReviewRequest,
    VerificationCheckResult,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
    DiagnosisStatus,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1CaseExecutionModel,
    C1CorrectionModel,
    C1ExecutionRunModel,
)
from app.components.c1_tool_call_correctness.services.correction_engine import (
    CorrectionEngine,
)
from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    ContainerSandbox,
    CorrectionSandbox,
    DisposableIsolatedSandbox,
)
from app.components.c1_tool_call_correctness.services.verification_engine import (
    VerificationEngine,
)


class CorrectionService:
    """Orchestrates candidate correction generation, sandbox isolation, verification, and review."""

    def __init__(
        self,
        correction_engine: CorrectionEngine | None = None,
        verification_engine: VerificationEngine | None = None,
    ):
        self.correction_engine = correction_engine or CorrectionEngine()
        self.verification_engine = verification_engine or VerificationEngine()

    def _model_to_record(self, model: C1CorrectionModel) -> CorrectionRecord:
        patch_obj = (
            CandidatePatch(**model.candidate_patch) if model.candidate_patch else None
        )
        ver_results = [
            VerificationCheckResult(**v) for v in (model.verification_results or [])
        ]
        rev_obj = ReviewRecord(**(model.review or {}))

        return CorrectionRecord(
            correction_id=model.id,
            project_id=model.project_id,
            run_id=model.run_id,
            case_id=model.case_id,
            case_execution_id=model.case_execution_id,
            diagnosis_id=model.diagnosis_id,
            attempt_number=model.attempt_number,
            source_hash=model.source_hash,
            source_commit=model.source_commit,
            permitted_paths=model.permitted_paths or [],
            candidate_patch=patch_obj,
            status=CorrectionStatus(model.status),
            is_verified=model.is_verified,
            ineligibility_reasons=model.ineligibility_reasons or [],
            verification_results=ver_results,
            review=rev_obj,
            isolation_type=model.isolation_type,
            metrics=model.metrics or {},
            created_at=model.created_at,
            completed_at=model.completed_at,
        )

    def check_eligibility(
        self,
        diagnosis: CaseDiagnosisRecord,
        source_root_path: Path | None,
        allowed_paths: list[str] | None,
    ) -> tuple[bool, list[str]]:
        """Verify whether a failure diagnosis meets all strict requirements for automated code correction.
        Requirements:
        1. Original recorded failure.
        2. Cause is strictly SUPPORTED_APPLICATION_CODE_DEFECT.
        3. Identifiable, available source snapshot.
        4. Permitted code paths.
        """
        reasons: list[str] = []

        # 1. Cause category check
        if diagnosis.cause_category != CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT:
            reasons.append(
                f"Diagnosis cause category is '{diagnosis.cause_category.value}'. "
                "Only verified SUPPORTED_APPLICATION_CODE_DEFECT failures are eligible for automated code correction."
            )

        # 2. Candidate code locations check
        if not diagnosis.candidate_code_locations:
            reasons.append(
                "Diagnosis contains no candidate code locations corroborated by AST source inspection."
            )

        # 3. Source snapshot check
        if not source_root_path or not source_root_path.is_dir():
            reasons.append(
                f"Source snapshot directory is unavailable or invalid: {source_root_path}."
            )

        # 4. Permitted paths check
        if allowed_paths is not None and diagnosis.candidate_code_locations:
            top_cand = diagnosis.candidate_code_locations[0]
            norm_cand = os.path.normpath(top_cand.file_path).replace("\\", "/")
            norm_allowed = [
                os.path.normpath(p).replace("\\", "/") for p in allowed_paths
            ]
            if norm_cand not in norm_allowed and not any(
                norm_cand.startswith(f"{a}/") for a in norm_allowed
            ):
                reasons.append(
                    f"Candidate code location '{top_cand.file_path}' is not within permitted paths: {allowed_paths}."
                )

        return (len(reasons) == 0), reasons

    async def execute_correction_attempt(
        self,
        db: Session,
        project_id: str,
        request: CorrectionAttemptRequest,
    ) -> CorrectionRecord:
        """Execute a single bounded candidate correction attempt with independent sandbox verification."""
        start_time = time.perf_counter()

        # 1. Idempotency check: if matching idempotency_key exists, return stored record
        if request.idempotency_key:
            existing = (
                db.execute(
                    select(C1CorrectionModel).filter(
                        C1CorrectionModel.project_id == project_id,
                        C1CorrectionModel.idempotency_key == request.idempotency_key,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                return self._model_to_record(existing)

        # 2. Retrieve corroborating diagnosis model
        diag_model = (
            db.execute(
                select(C1CaseDiagnosisModel).filter(
                    C1CaseDiagnosisModel.project_id == project_id,
                    C1CaseDiagnosisModel.id == request.diagnosis_id,
                )
            )
            .scalars()
            .first()
        )
        if not diag_model:
            raise ValueError(
                f"Diagnosis '{request.diagnosis_id}' not found for project '{project_id}'."
            )

        # Convert to CaseDiagnosisRecord
        diag_record = CaseDiagnosisRecord(
            diagnosis_id=diag_model.id,
            project_id=diag_model.project_id,
            run_id=diag_model.run_id,
            case_execution_id=diag_model.case_execution_id,
            case_id=diag_model.case_id,
            attempt_number=diag_model.attempt_number,
            requirement_version=diag_model.requirement_version,
            evaluator_version=diag_model.evaluator_version,
            explanation_version=diag_model.explanation_version,
            status=DiagnosisStatus(diag_model.status),
            cause_category=CauseCategory(diag_model.cause_category),
            explanation_summary=diag_model.explanation_summary,
            check_explanations=diag_model.check_explanations,
            candidate_code_locations=[
                CandidateCodeLocation(**c)
                for c in (diag_model.candidate_code_locations or [])
            ],
            evidence_refs=diag_model.evidence_refs or [],
            source_hash=diag_model.source_hash,
            explanation_method=diag_model.explanation_method,
            metrics=diag_model.metrics or {},
            created_at=diag_model.created_at,
        )

        # Retrieve original case execution
        case_exec_model = (
            db.execute(
                select(C1CaseExecutionModel).filter(
                    C1CaseExecutionModel.id == diag_model.case_execution_id
                )
            )
            .scalars()
            .first()
        )
        if not case_exec_model:
            raise ValueError(
                f"Case execution '{diag_model.case_execution_id}' not found."
            )

        # Determine next attempt number
        prev_attempts = (
            db.execute(
                select(C1CorrectionModel).filter(
                    C1CorrectionModel.run_id == diag_model.run_id,
                    C1CorrectionModel.case_id == diag_model.case_id,
                )
            )
            .scalars()
            .all()
        )
        attempt_number = len(prev_attempts) + 1

        source_root = (
            Path(request.source_root_path) if request.source_root_path else None
        )

        # 3. Eligibility Verification
        is_eligible, ineligibility_reasons = self.check_eligibility(
            diagnosis=diag_record,
            source_root_path=source_root,
            allowed_paths=request.allowed_paths,
        )

        correction_id = f"corr_{uuid.uuid4().hex[:12]}"

        # If ineligible: create INELIGIBLE record without touching source or generating patches
        if not is_eligible:
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0
            ineligible_model = C1CorrectionModel(
                id=correction_id,
                project_id=project_id,
                run_id=diag_model.run_id,
                case_execution_id=diag_model.case_execution_id,
                case_id=diag_model.case_id,
                diagnosis_id=diag_model.id,
                attempt_number=attempt_number,
                source_hash=diag_record.source_hash,
                source_commit=request.code_version,
                permitted_paths=request.allowed_paths or [],
                candidate_patch=None,
                status=CorrectionStatus.INELIGIBLE.value,
                is_verified=False,
                ineligibility_reasons=ineligibility_reasons,
                verification_results=[],
                review={"decision": ReviewDecision.PENDING.value},
                isolation_type="NONE",
                metrics={"total_duration_ms": round(total_duration_ms, 2)},
                idempotency_key=request.idempotency_key,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db.add(ineligible_model)
            db.commit()
            return self._model_to_record(ineligible_model)

        # 4. Prepare Sandbox and Isolation
        sandbox: CorrectionSandbox
        isolation_type_str: str

        if request.force_container_isolation:
            sandbox = ContainerSandbox()
            isolation_type_str = "CONTAINER"
            is_ready, ready_err = sandbox.check_readiness()
            if not is_ready:
                total_duration_ms = (time.perf_counter() - start_time) * 1000.0
                blocked_model = C1CorrectionModel(
                    id=correction_id,
                    project_id=project_id,
                    run_id=diag_model.run_id,
                    case_execution_id=diag_model.case_execution_id,
                    case_id=diag_model.case_id,
                    diagnosis_id=diag_model.id,
                    attempt_number=attempt_number,
                    source_hash=diag_record.source_hash,
                    source_commit=request.code_version,
                    permitted_paths=request.allowed_paths or [],
                    candidate_patch=None,
                    status=CorrectionStatus.UNVERIFIED.value,
                    is_verified=False,
                    ineligibility_reasons=[
                        f"Container isolation unavailable: {ready_err}"
                    ],
                    verification_results=[],
                    review={"decision": ReviewDecision.PENDING.value},
                    isolation_type=isolation_type_str,
                    metrics={"total_duration_ms": round(total_duration_ms, 2)},
                    idempotency_key=request.idempotency_key,
                    created_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
                db.add(blocked_model)
                db.commit()
                return self._model_to_record(blocked_model)
        else:
            sandbox = DisposableIsolatedSandbox()
            isolation_type_str = "DISPOSABLE_SUBPROCESS"

        # 5. Retrieve Tool Definitions from Run Config
        run_model = (
            db.execute(
                select(C1ExecutionRunModel)
                .options(joinedload(C1ExecutionRunModel.config))
                .filter(C1ExecutionRunModel.id == diag_model.run_id)
            )
            .unique()
            .scalar_one_or_none()
        )
        tools_list = run_model.config.tools if (run_model and run_model.config) else []
        tool_defs = {t["name"]: ToolDefinition(**t) for t in tools_list}

        # 6. Bounded Patch Generation
        gen_start = time.perf_counter()
        candidate_patch, gen_err = self.correction_engine.generate_patch(
            diagnosis=diag_record,
            source_root_path=source_root,  # type: ignore
            tool_definitions=tool_defs,
            allowed_paths=request.allowed_paths,
            patch_override=request.patch_override,
        )
        gen_duration_ms = (time.perf_counter() - gen_start) * 1000.0

        if not candidate_patch:
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0
            failed_model = C1CorrectionModel(
                id=correction_id,
                project_id=project_id,
                run_id=diag_model.run_id,
                case_execution_id=diag_model.case_execution_id,
                case_id=diag_model.case_id,
                diagnosis_id=diag_model.id,
                attempt_number=attempt_number,
                source_hash=diag_record.source_hash,
                source_commit=request.code_version,
                permitted_paths=request.allowed_paths or [],
                candidate_patch=None,
                status=CorrectionStatus.FAILED.value,
                is_verified=False,
                ineligibility_reasons=[gen_err or "Patch generation failed."],
                verification_results=[],
                review={"decision": ReviewDecision.PENDING.value},
                isolation_type=isolation_type_str,
                metrics={
                    "generation_duration_ms": round(gen_duration_ms, 2),
                    "total_duration_ms": round(total_duration_ms, 2),
                },
                idempotency_key=request.idempotency_key,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db.add(failed_model)
            db.commit()
            return self._model_to_record(failed_model)

        # 7. Create Disposable Application Copy for Sandbox Execution
        scratch_dir = Path(tempfile.mkdtemp(prefix="c1_sandbox_"))
        try:
            # Copy source tree into scratch workspace
            shutil.copytree(source_root, scratch_dir / "repo", dirs_exist_ok=True)  # type: ignore
            disposable_workspace = scratch_dir / "repo"

            # Parse original case execution detail
            original_case_detail = CaseExecutionDetail(
                execution_id=case_exec_model.id,
                case_id=case_exec_model.case_id,
                attempt_number=case_exec_model.attempt_number,
                session_id=case_exec_model.session_id,
                readiness_status=case_exec_model.readiness_status,
                execution_status=case_exec_model.execution_status,
                verdict=case_exec_model.verdict,
                trace_completeness=case_exec_model.trace_completeness,
                resolved_expectations=case_exec_model.resolved_expectations or [],
                agent_task_sent=case_exec_model.agent_task_sent,
                captured_events=case_exec_model.captured_events or [],
                check_results=case_exec_model.check_results or [],
            )

            # Find failing check
            failing_check: CheckLevelResult | None = None
            for chk in original_case_detail.check_results:
                if chk.verdict in (
                    CorrectnessVerdict.FAIL,
                    CorrectnessVerdict.INCONCLUSIVE,
                ):
                    failing_check = chk
                    break

            # Execute verification plan
            ver_start = time.perf_counter()
            (
                is_verified,
                ver_status,
                ver_results,
            ) = await self.verification_engine.execute_plan(
                disposable_workspace=disposable_workspace,
                candidate_patch=candidate_patch,
                original_case=original_case_detail,
                original_failing_check=failing_check,
                regression_cases=[],  # can include other run cases
                hidden_acceptance_case=None,
                sandbox=sandbox,
            )
            ver_duration_ms = (time.perf_counter() - ver_start) * 1000.0

        finally:
            # Strictly clean up temporary disposable sandbox files
            shutil.rmtree(scratch_dir, ignore_errors=True)

        total_duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 8. Persist Correction Attempt Model
        correction_model = C1CorrectionModel(
            id=correction_id,
            project_id=project_id,
            run_id=diag_model.run_id,
            case_execution_id=diag_model.case_execution_id,
            case_id=diag_model.case_id,
            diagnosis_id=diag_model.id,
            attempt_number=attempt_number,
            source_hash=diag_record.source_hash,
            source_commit=request.code_version,
            permitted_paths=request.allowed_paths or [],
            candidate_patch=candidate_patch.model_dump(mode="json"),
            status=ver_status.value,
            is_verified=is_verified,
            ineligibility_reasons=[],
            verification_results=[v.model_dump(mode="json") for v in ver_results],
            review={"decision": ReviewDecision.PENDING.value},
            isolation_type=isolation_type_str,
            metrics={
                "generation_duration_ms": round(gen_duration_ms, 2),
                "verification_duration_ms": round(ver_duration_ms, 2),
                "total_duration_ms": round(total_duration_ms, 2),
            },
            idempotency_key=request.idempotency_key,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db.add(correction_model)
        db.commit()
        return self._model_to_record(correction_model)

    def get_correction_by_id(
        self, db: Session, project_id: str, correction_id: str
    ) -> CorrectionRecord | None:
        """Retrieve correction attempt record by ID."""
        model = (
            db.execute(
                select(C1CorrectionModel).filter(
                    C1CorrectionModel.project_id == project_id,
                    C1CorrectionModel.id == correction_id,
                )
            )
            .scalars()
            .first()
        )
        if not model:
            return None
        return self._model_to_record(model)

    def get_correction_diff(
        self, db: Session, project_id: str, correction_id: str
    ) -> CorrectionDiffResponse:
        """Retrieve diff representation and metadata for developer review."""
        record = self.get_correction_by_id(db, project_id, correction_id)
        if not record:
            raise ValueError(f"Correction '{correction_id}' not found.")

        if not record.candidate_patch:
            return CorrectionDiffResponse(
                correction_id=correction_id,
                diff_content="",
                is_verified=record.is_verified,
                review_decision=record.review.decision,
            )

        patch = record.candidate_patch
        return CorrectionDiffResponse(
            correction_id=correction_id,
            patch_id=patch.patch_id,
            patch_hash=patch.patch_hash,
            source_hash=record.source_hash,
            diff_content=patch.diff_content,
            modified_files=patch.modified_files,
            is_verified=record.is_verified,
            review_decision=record.review.decision,
        )

    def submit_review(
        self,
        db: Session,
        project_id: str,
        correction_id: str,
        request: ReviewRequest,
    ) -> CorrectionRecord:
        """Record an explicit developer review decision.
        Binds decision strictly to the exact patch hash and requires verified status for acceptance.
        Does NOT silently merge or deploy to project repository.
        """
        model = (
            db.execute(
                select(C1CorrectionModel).filter(
                    C1CorrectionModel.project_id == project_id,
                    C1CorrectionModel.id == correction_id,
                )
            )
            .scalars()
            .first()
        )
        if not model:
            raise ValueError(f"Correction '{correction_id}' not found.")

        patch_data = model.candidate_patch or {}
        actual_hash = patch_data.get("patch_hash")

        # Stale or mismatched review target check
        if request.target_patch_hash != actual_hash:
            raise ValueError(
                f"Review target mismatch: Submitted patch hash '{request.target_patch_hash}' "
                f"does not match candidate patch hash '{actual_hash}'."
            )

        # Acceptance check: Only VERIFIED candidates can be accepted
        if request.decision == ReviewDecision.ACCEPTED and not model.is_verified:
            raise ValueError(
                "Unverified candidates cannot be accepted. "
                "Only candidates where every mandatory verification check passed are eligible for acceptance."
            )

        # Record review decision
        audit_ref = f"audit_rev_{uuid.uuid4().hex[:8]}"
        model.review = {
            "decision": request.decision.value,
            "reviewer": request.reviewer,
            "reason": request.reason,
            "target_patch_hash": request.target_patch_hash,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "audit_ref": audit_ref,
        }
        db.commit()
        return self._model_to_record(model)

    def list_corrections(
        self,
        db: Session,
        project_id: str,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[CorrectionSummary]:
        """Inspect correction history for a project or run."""
        stmt = (
            select(C1CorrectionModel)
            .filter(C1CorrectionModel.project_id == project_id)
            .order_by(desc(C1CorrectionModel.created_at))
            .limit(limit)
        )
        if run_id:
            stmt = stmt.filter(C1CorrectionModel.run_id == run_id)

        models = db.execute(stmt).scalars().all()
        return [
            CorrectionSummary(
                correction_id=m.id,
                project_id=m.project_id,
                run_id=m.run_id,
                case_id=m.case_id,
                diagnosis_id=m.diagnosis_id,
                attempt_number=m.attempt_number,
                status=CorrectionStatus(m.status),
                is_verified=m.is_verified,
                review_decision=ReviewDecision(
                    (m.review or {}).get("decision", ReviewDecision.PENDING.value)
                ),
                created_at=m.created_at,
            )
            for m in models
        ]
