"""Correction attempts for NexaCart runs: bounded patch now, live sandbox verification in background.

Component: C1 - Explainable Tool-Call Correctness Testing

Only a diagnosis of SUPPORTED_APPLICATION_CODE_DEFECT with a located TypeScript tool function is
eligible. The source tree is the server-side one the run's configuration names (the controlled
defect lab copy, or ``NEXACART_SOURCE_ROOT``); a path sent by the browser is never used. The
candidate is persisted as VERIFYING and ``verify_attempt`` records each verification step as it
finishes, so the page can follow a verification that takes several minutes.
"""

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.correction import (
    CorrectionAttemptRequest,
    CorrectionStatus,
    ReviewDecision,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CaseDiagnosisRecord,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseExecutionModel,
    C1CorrectionModel,
    C1ExecutionRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.correction_engine import (
    CorrectionEngine,
    validate_patch_content,
)
from app.components.c1_tool_call_correctness.services.nexacart_correction import (
    NexaCartVerificationEngine,
    TypeScriptMappingPatchGenerator,
    acceptance_case_for,
    is_lab_workspace,
)

ISOLATION_TYPE = "DISPOSABLE_NEXACART_COPY_LIVE"


def nexacart_source_root(config: C1ProjectConfigModel | None) -> Path | None:
    """Server-side NexaCart source tree for a configuration (lab copy or configured root)."""
    from app.config import get_settings

    details = ((config.reset_capability or {}) if config else {}).get("details") or {}
    lab_root = details.get("source_root")
    if lab_root and is_lab_workspace(lab_root) and Path(lab_root).is_dir():
        return Path(lab_root)
    configured = get_settings().nexacart_source_root
    return Path(configured) if configured and Path(configured).is_dir() else None


def _tool_for_location(
    config: C1ProjectConfigModel, file_path: str
) -> ToolDefinition | None:
    for tool in config.tools or []:
        mapping = tool.get("code_mapping") or {}
        if mapping.get("file_path") == file_path:
            return ToolDefinition(**tool)
    return None


def start_attempt(
    service: Any,
    db: Session,
    project_id: str,
    request: CorrectionAttemptRequest,
    diagnosis: CaseDiagnosisRecord,
    case_execution: C1CaseExecutionModel,
    run_model: C1ExecutionRunModel,
    attempt_number: int,
    schedule: Callable[[str], None] | None,
) -> C1CorrectionModel:
    """Eligibility + one candidate patch; persists the attempt and schedules verification."""
    started = time.perf_counter()
    config = run_model.config
    source_root = nexacart_source_root(config)
    location = (
        min(diagnosis.candidate_code_locations, key=lambda c: c.ranking_score)
        if diagnosis.candidate_code_locations
        else None
    )
    allowed = request.allowed_paths or ([location.file_path] if location else [])

    def persist(
        status: CorrectionStatus, reasons: list[str], patch=None
    ) -> C1CorrectionModel:
        record = C1CorrectionModel(
            id=f"corr_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            run_id=run_model.id,
            case_execution_id=case_execution.id,
            case_id=case_execution.case_id,
            diagnosis_id=diagnosis.diagnosis_id,
            attempt_number=attempt_number,
            source_hash=diagnosis.source_hash,
            source_commit=request.code_version,
            permitted_paths=allowed,
            candidate_patch=patch.model_dump(mode="json") if patch else None,
            status=status.value,
            is_verified=False,
            ineligibility_reasons=reasons,
            verification_results=[],
            review={"decision": ReviewDecision.PENDING.value},
            isolation_type=ISOLATION_TYPE if patch else "NONE",
            metrics={
                "generation_duration_ms": round(
                    (time.perf_counter() - started) * 1000, 1
                ),
                "source_tree": "controlled_defect_lab"
                if source_root and is_lab_workspace(source_root)
                else "nexacart_source_root",
            },
            idempotency_key=request.idempotency_key,
            created_at=datetime.now(UTC),
            completed_at=None
            if status == CorrectionStatus.VERIFYING
            else datetime.now(UTC),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    from app.config import get_settings

    if not get_settings().c1_code_correction_enabled:
        return persist(
            CorrectionStatus.INELIGIBLE,
            [
                (
                    "Code correction and sandbox verification are disabled in this build "
                    "(C1_CODE_CORRECTION_ENABLED=false)."
                )
            ],
        )
    eligible, reasons = service.check_eligibility(diagnosis, source_root, allowed)
    if source_root is None:
        reasons.append(
            "No server-side NexaCart source tree: set NEXACART_SOURCE_ROOT or use the defect lab."
        )
        eligible = False
    tool = (
        _tool_for_location(config, location.file_path)
        if (config and location)
        else None
    )
    if eligible and tool is None:
        eligible = False
        reasons.append("The located file is not the code mapping of a configured tool.")
    if not eligible:
        return persist(CorrectionStatus.INELIGIBLE, reasons)

    if request.patch_override:
        patch, error = CorrectionEngine().generate_patch(
            diagnosis, source_root, {}, allowed, request.patch_override
        )
    else:
        patch = TypeScriptMappingPatchGenerator().generate_candidate_patch(
            diagnosis, location, source_root, tool
        )
        error = (
            None
            if patch
            else "No bounded TypeScript patch can repair the located defect."
        )
        if patch:
            ok, err, *_ = validate_patch_content(patch.diff_content, allowed)
            if not ok:
                patch, error = (
                    None,
                    f"Synthesized patch failed safety validation: {err}",
                )
    if patch is None:
        return persist(CorrectionStatus.FAILED, [error or "Patch generation failed."])

    record = persist(CorrectionStatus.VERIFYING, [], patch)
    if schedule is not None:
        schedule(record.id)
    return record


async def verify_attempt(
    session_factory: Callable[[], Session],
    correction_id: str,
    adapter_factory: Callable[[str], Any],
) -> None:
    """Background job: run the six verification steps and persist each result immediately."""
    from app.components.c1_tool_call_correctness.contracts.correction import (
        CandidatePatch,
    )

    db = session_factory()
    started = time.perf_counter()
    try:
        record = db.get(C1CorrectionModel, correction_id)
        if record is None or record.candidate_patch is None:
            return
        case_exec = db.get(C1CaseExecutionModel, record.case_execution_id)
        run_model = db.get(C1ExecutionRunModel, record.run_id)
        suite = (
            db.get(C1SuiteVersionModel, run_model.suite_version_id)
            if run_model
            else None
        )
        config = run_model.config if run_model else None
        from app.components.c1_tool_call_correctness.models.persistence import (
            C1CaseDiagnosisModel,
        )

        diag_model = db.get(C1CaseDiagnosisModel, record.diagnosis_id)
        diagnosis = CaseDiagnosisRecord(
            diagnosis_id=diag_model.id,
            project_id=diag_model.project_id,
            run_id=diag_model.run_id,
            case_execution_id=diag_model.case_execution_id,
            case_id=diag_model.case_id,
            attempt_number=diag_model.attempt_number,
            requirement_version=diag_model.requirement_version,
            evaluator_version=diag_model.evaluator_version,
            explanation_version=diag_model.explanation_version,
            status=diag_model.status,
            cause_category=diag_model.cause_category,
            explanation_summary=diag_model.explanation_summary,
            check_explanations=diag_model.check_explanations,
            candidate_code_locations=diag_model.candidate_code_locations or [],
            evidence_refs=diag_model.evidence_refs or [],
            source_hash=diag_model.source_hash,
            explanation_method=diag_model.explanation_method,
        )
        source_root = nexacart_source_root(config)
        location = min(
            diagnosis.candidate_code_locations, key=lambda c: c.ranking_score
        )
        tool = _tool_for_location(config, location.file_path)
        base_case_id = case_exec.case_id.split("::r")[0]
        cases = suite.cases if suite else []
        original_case = next(
            (c for c in cases if c.get("case_id") == base_case_id), None
        )
        if source_root is None or tool is None or original_case is None:
            record.status = CorrectionStatus.UNVERIFIED.value
            record.ineligibility_reasons = [
                "Verification inputs are unavailable (source tree, tool mapping or the frozen case)."
            ]
            record.completed_at = datetime.now(UTC)
            db.commit()
            return
        acceptance = acceptance_case_for(
            config,
            tool.name,
            {c.get("case_id") for c in cases},
            {c.get("canonical_hash") for c in cases},
        )

        def on_step(result: Any) -> None:
            record.verification_results = [
                *(record.verification_results or []),
                result.model_dump(mode="json"),
            ]
            db.commit()

        engine = NexaCartVerificationEngine(adapter_factory)
        verified, status, _results, details = await engine.execute_plan(
            source_root=source_root,
            candidate_patch=CandidatePatch(**record.candidate_patch),
            diagnosis=diagnosis,
            tool_definition=tool,
            original_case=original_case,
            original_verdict=case_exec.verdict,
            acceptance_case=acceptance,
            tool_constraints=config.tool_constraints if config else None,
            on_step=on_step,
        )
        record.status = status.value
        record.is_verified = verified
        record.metrics = {
            **(record.metrics or {}),
            "verification_duration_ms": round(
                (time.perf_counter() - started) * 1000, 1
            ),
            "rerun": details.get("rerun"),
            "acceptance": details.get("acceptance"),
        }
        record.completed_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        record = db.get(C1CorrectionModel, correction_id)
        if record is not None:
            record.status = CorrectionStatus.UNVERIFIED.value
            record.ineligibility_reasons = [
                *(record.ineligibility_reasons or []),
                f"Verification stopped by an internal error: {exc}",
            ]
            record.completed_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def is_nexacart_run(db: Session, run_id: str) -> C1ExecutionRunModel | None:
    from app.components.c1_tool_call_correctness.examples.nexacart_live import (
        is_nexacart_connection,
    )

    run_model = db.execute(
        select(C1ExecutionRunModel).where(C1ExecutionRunModel.id == run_id)
    ).scalar_one_or_none()
    if (
        run_model
        and run_model.config
        and is_nexacart_connection(run_model.config.agent_connection_ref)
    ):
        return run_model
    return None
