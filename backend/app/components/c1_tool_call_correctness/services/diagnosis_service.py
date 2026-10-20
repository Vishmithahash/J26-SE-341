import time

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    DiagnosisRequest,
    DiagnosisStatus,
    DiagnosisSummary,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1ExecutionRunModel,
)
from app.components.c1_tool_call_correctness.services.diagnosis_engine import (
    DiagnosisEngine,
)
from app.components.c1_tool_call_correctness.services.diagnosis_provider import (
    DeterministicDiagnosisProvider,
    DiagnosisProvider,
    ModelAssistedDiagnosisProvider,
)
from app.components.c1_tool_call_correctness.services.explanation_engine import (
    ExplanationEngine,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspector,
)


class DiagnosisService:
    """Orchestrates evidence-linked explanations, root-cause diagnosis, and persistence."""

    def __init__(
        self,
        explanation_engine: ExplanationEngine | None = None,
        diagnosis_engine: DiagnosisEngine | None = None,
        default_provider: DiagnosisProvider | None = None,
    ):
        self.explanation_engine = explanation_engine or ExplanationEngine()
        self.diagnosis_engine = diagnosis_engine or DiagnosisEngine()
        self.default_provider = default_provider or DeterministicDiagnosisProvider()

    def _model_to_record(self, model: C1CaseDiagnosisModel) -> CaseDiagnosisRecord:
        return CaseDiagnosisRecord(
            diagnosis_id=model.id,
            project_id=model.project_id,
            run_id=model.run_id,
            case_execution_id=model.case_execution_id,
            case_id=model.case_id,
            attempt_number=model.attempt_number,
            requirement_version=model.requirement_version,
            evaluator_version=model.evaluator_version,
            explanation_version=model.explanation_version,
            status=DiagnosisStatus(model.status),
            cause_category=model.cause_category,
            explanation_summary=model.explanation_summary,
            check_explanations=model.check_explanations,
            candidate_code_locations=model.candidate_code_locations,
            evidence_refs=model.evidence_refs,
            source_hash=model.source_hash,
            explanation_method=model.explanation_method,
            metrics=model.metrics,
            created_at=model.created_at,
        )

    async def execute_diagnosis(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        request: DiagnosisRequest,
    ) -> list[CaseDiagnosisRecord]:
        """Perform batch failure explanation and diagnosis for an execution run."""
        # 1. Check idempotency: If idempotency_key is provided and existing records match, return immediately
        if request.idempotency_key:
            existing_records = (
                db.execute(
                    select(C1CaseDiagnosisModel).filter(
                        C1CaseDiagnosisModel.project_id == project_id,
                        C1CaseDiagnosisModel.run_id == run_id,
                        C1CaseDiagnosisModel.idempotency_key == request.idempotency_key,
                    )
                )
                .scalars()
                .all()
            )
            if existing_records:
                return [self._model_to_record(m) for m in existing_records]

        # 2. Batch-retrieve execution run, case executions, and config in a single query
        retrieval_start = time.perf_counter()
        stmt = (
            select(C1ExecutionRunModel)
            .options(
                joinedload(C1ExecutionRunModel.case_executions),
                joinedload(C1ExecutionRunModel.config),
            )
            .filter(
                C1ExecutionRunModel.project_id == project_id,
                C1ExecutionRunModel.id == run_id,
            )
        )
        run_model = db.execute(stmt).unique().scalar_one_or_none()
        if not run_model:
            raise ValueError(
                f"Execution run '{run_id}' not found for project '{project_id}'."
            )

        retrieval_duration_ms = (time.perf_counter() - retrieval_start) * 1000.0

        # Build tool definitions map
        tools_list = run_model.config.tools if run_model.config else []
        tool_defs: dict[str, ToolDefinition] = {
            t["name"]: ToolDefinition(**t) for t in tools_list
        }

        # Initialize SourceInspector if source_root_path provided
        source_inspector: SourceInspector | None = None
        if request.source_root_path:
            source_inspector = SourceInspector(request.source_root_path)

        # Provider selection
        provider = self.default_provider
        if request.use_model_assisted:
            provider = ModelAssistedDiagnosisProvider()

        results: list[CaseDiagnosisRecord] = []

        # Filter case executions
        target_case_models = run_model.case_executions
        if request.case_id:
            target_case_models = [
                cm for cm in target_case_models if cm.case_id == request.case_id
            ]
            if not target_case_models:
                raise ValueError(
                    f"Case '{request.case_id}' not found in run '{run_id}'."
                )

        # Process each case execution
        for case_model in target_case_models:
            case_detail = CaseExecutionDetail(
                execution_id=case_model.id,
                case_id=case_model.case_id,
                attempt_number=case_model.attempt_number,
                session_id=case_model.session_id,
                readiness_status=case_model.readiness_status,
                execution_status=case_model.execution_status,
                verdict=case_model.verdict,
                trace_completeness=case_model.trace_completeness,
                resolved_expectations=case_model.resolved_expectations or [],
                agent_task_sent=case_model.agent_task_sent,
                captured_events=case_model.captured_events or [],
                evidence_records=case_model.evidence_records or [],
                raw_trace=case_model.raw_trace or {},
                check_results=case_model.check_results or [],
                error_message=case_model.error_message,
                created_at=case_model.created_at,
                completed_at=case_model.completed_at,
            )

            # Generate deterministic check explanations
            check_explanations = self.explanation_engine.explain_case_checks(
                check_results=case_detail.check_results,
                captured_events=case_detail.captured_events,
                trace_completeness=case_detail.trace_completeness,
            )

            # Diagnose supported root cause
            diagnosis_record = self.diagnosis_engine.diagnose_case(
                project_id=project_id,
                run_id=run_id,
                case_execution=case_detail,
                check_explanations=check_explanations,
                tool_definitions=tool_defs,
                source_inspector=source_inspector,
                expected_code_version=request.code_version,
                retrieval_duration_ms=retrieval_duration_ms,
            )

            # Present diagnosis summary through provider (deterministic or model-assisted)
            presentation_result = await provider.present_diagnosis(diagnosis_record)
            diagnosis_record.explanation_summary = (
                presentation_result.explanation_summary
            )
            diagnosis_record.explanation_method = presentation_result.explanation_method
            if presentation_result.metrics.model_name != "deterministic-rule-engine":
                diagnosis_record.metrics["model_metrics"] = (
                    presentation_result.metrics.model_dump()
                )

            # Check if an existing diagnosis record already exists for this run/case/attempt
            existing_diag = (
                db.execute(
                    select(C1CaseDiagnosisModel).filter(
                        C1CaseDiagnosisModel.run_id == run_id,
                        C1CaseDiagnosisModel.case_id == case_model.case_id,
                        C1CaseDiagnosisModel.attempt_number
                        == case_model.attempt_number,
                        C1CaseDiagnosisModel.explanation_version
                        == diagnosis_record.explanation_version,
                    )
                )
                .scalars()
                .first()
            )

            if existing_diag:
                # Update existing record
                existing_diag.status = diagnosis_record.status.value
                existing_diag.cause_category = diagnosis_record.cause_category.value
                existing_diag.explanation_summary = diagnosis_record.explanation_summary
                existing_diag.check_explanations = [
                    c.model_dump(mode="json")
                    for c in diagnosis_record.check_explanations
                ]
                existing_diag.candidate_code_locations = [
                    c.model_dump(mode="json")
                    for c in diagnosis_record.candidate_code_locations
                ]
                existing_diag.evidence_refs = diagnosis_record.evidence_refs
                existing_diag.source_hash = diagnosis_record.source_hash
                existing_diag.explanation_method = (
                    diagnosis_record.explanation_method.value
                )
                existing_diag.metrics = diagnosis_record.metrics
                existing_diag.idempotency_key = request.idempotency_key
                db.flush()
                results.append(self._model_to_record(existing_diag))
            else:
                # Insert new diagnosis model
                new_diag = C1CaseDiagnosisModel(
                    id=diagnosis_record.diagnosis_id,
                    project_id=project_id,
                    run_id=run_id,
                    case_execution_id=case_model.id,
                    case_id=case_model.case_id,
                    attempt_number=case_model.attempt_number,
                    requirement_version=diagnosis_record.requirement_version,
                    evaluator_version=diagnosis_record.evaluator_version,
                    explanation_version=diagnosis_record.explanation_version,
                    status=diagnosis_record.status.value,
                    cause_category=diagnosis_record.cause_category.value,
                    explanation_summary=diagnosis_record.explanation_summary,
                    check_explanations=[
                        c.model_dump(mode="json")
                        for c in diagnosis_record.check_explanations
                    ],
                    candidate_code_locations=[
                        c.model_dump(mode="json")
                        for c in diagnosis_record.candidate_code_locations
                    ],
                    evidence_refs=diagnosis_record.evidence_refs,
                    source_hash=diagnosis_record.source_hash,
                    explanation_method=diagnosis_record.explanation_method.value,
                    metrics=diagnosis_record.metrics,
                    idempotency_key=request.idempotency_key,
                )
                db.add(new_diag)
                db.flush()
                results.append(self._model_to_record(new_diag))

        db.commit()
        return results

    def get_diagnosis_by_id(
        self, db: Session, project_id: str, diagnosis_id: str
    ) -> CaseDiagnosisRecord | None:
        """Retrieve a stored diagnosis record by diagnosis ID."""
        model = (
            db.execute(
                select(C1CaseDiagnosisModel).filter(
                    C1CaseDiagnosisModel.project_id == project_id,
                    C1CaseDiagnosisModel.id == diagnosis_id,
                )
            )
            .scalars()
            .first()
        )
        if not model:
            return None
        return self._model_to_record(model)

    def get_case_diagnosis(
        self, db: Session, project_id: str, run_id: str, case_id: str
    ) -> CaseDiagnosisRecord | None:
        """Retrieve latest diagnosis for a specific case execution in a run."""
        model = (
            db.execute(
                select(C1CaseDiagnosisModel)
                .filter(
                    C1CaseDiagnosisModel.project_id == project_id,
                    C1CaseDiagnosisModel.run_id == run_id,
                    C1CaseDiagnosisModel.case_id == case_id,
                )
                .order_by(desc(C1CaseDiagnosisModel.attempt_number))
            )
            .scalars()
            .first()
        )
        if not model:
            return None
        return self._model_to_record(model)

    def get_candidate_code_locations(
        self, db: Session, project_id: str, diagnosis_id: str
    ) -> list[CandidateCodeLocation]:
        """Retrieve evidence-linked candidate code locations for a diagnosis."""
        diag = self.get_diagnosis_by_id(db, project_id, diagnosis_id)
        if not diag:
            raise ValueError(f"Diagnosis '{diagnosis_id}' not found.")
        return diag.candidate_code_locations

    def list_diagnoses(
        self,
        db: Session,
        project_id: str,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[DiagnosisSummary]:
        """Inspect diagnosis history for a project or run."""
        stmt = (
            select(C1CaseDiagnosisModel)
            .filter(C1CaseDiagnosisModel.project_id == project_id)
            .order_by(desc(C1CaseDiagnosisModel.created_at))
            .limit(limit)
        )
        if run_id:
            stmt = stmt.filter(C1CaseDiagnosisModel.run_id == run_id)

        models = db.execute(stmt).scalars().all()
        return [
            DiagnosisSummary(
                diagnosis_id=m.id,
                project_id=m.project_id,
                run_id=m.run_id,
                case_execution_id=m.case_execution_id,
                case_id=m.case_id,
                attempt_number=m.attempt_number,
                cause_category=m.cause_category,
                explanation_summary=m.explanation_summary,
                candidate_count=len(m.candidate_code_locations or []),
                status=DiagnosisStatus(m.status),
                created_at=m.created_at,
            )
            for m in models
        ]
