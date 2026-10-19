"""Execution tracking service integrating runner lifecycle with C3 persistence.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionArtifactImportRequest,
    ExecutionCreateRequest,
    ExecutionRecordResponse,
    ExecutionTrackingStatus,
    PaginatedResponse,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    MatchedPairEvidence,
    sanitize_arguments,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import (
    SuiteExecutionSummary,
)


def create_execution_manifest(
    db: Session, project_id: str, request: ExecutionCreateRequest
) -> ExecutionRecordResponse:
    """Validate suite exists and persist initial planned execution manifest.

    Executed in a short transaction before any runner or target activity starts.
    """
    repo = C3PersistenceRepository(db)

    # 1. Enforce that referenced suite exists in project scope
    suite_model = repo.get_suite_by_digest(project_id, request.suite_digest)
    if not suite_model:
        raise EntityNotFoundError(
            f"Referenced suite digest '{request.suite_digest}' does not exist in project '{project_id}'."
        )

    # 2. Persist execution record
    exec_model, _ = repo.create_or_get_execution(
        project_id=project_id,
        request=request,
        suite_id=suite_model.suite_id,
    )
    db.commit()

    return ExecutionRecordResponse(
        execution_id=exec_model.execution_id,
        suite_digest=exec_model.suite_digest,
        suite_id=exec_model.suite_id,
        project_id=exec_model.project_id,
        target_mode=exec_model.target_mode,
        caller_identity=exec_model.caller_identity,
        status=ExecutionTrackingStatus(exec_model.status),
        planned_cases_count=exec_model.planned_cases_count,
        executed_cases_count=exec_model.executed_cases_count,
        blocked_cases_count=exec_model.blocked_cases_count,
        unsupported_cases_count=exec_model.unsupported_cases_count,
        cancelled_cases_count=exec_model.cancelled_cases_count,
        error_cases_count=exec_model.error_cases_count,
        halt_reason=exec_model.halt_reason,
        started_at_utc=exec_model.started_at_utc.isoformat(),
        completed_at_utc=exec_model.completed_at_utc.isoformat()
        if exec_model.completed_at_utc
        else None,
        manifest_snapshot=exec_model.manifest_snapshot,
    )


def import_execution_artifact(
    db: Session, request: ExecutionArtifactImportRequest
) -> ExecutionRecordResponse:
    """Transactionally import a completed or partial execution artifact and its evidences.

    Does not trigger target or harness execution.
    """
    repo = C3PersistenceRepository(db)

    # Verify suite exists
    suite_model = repo.get_suite_by_digest(request.project_id, request.suite_digest)
    if not suite_model:
        raise EntityNotFoundError(
            f"Referenced suite digest '{request.suite_digest}' does not exist in project '{request.project_id}'."
        )

    create_req = ExecutionCreateRequest(
        execution_id=request.execution_id,
        suite_digest=request.suite_digest,
        project_id=request.project_id,
        target_mode=request.target_mode,
        caller_identity=request.caller_identity,
        planned_cases=request.manifest_snapshot.get("planned_cases", []),
        configuration_snapshot=request.manifest_snapshot.get("configuration", {}),
    )

    exec_model, _ = repo.create_or_get_execution(
        project_id=request.project_id,
        request=create_req,
        suite_id=suite_model.suite_id,
    )

    # Import any associated pair evidences transactionally
    for ev in request.case_evidences:
        validate_evidence_linkage(ev)
        repo.save_matched_pair(
            project_id=request.project_id,
            evidence=ev,
            execution_id=exec_model.execution_id,
        )

    exec_model = repo.update_execution_progress(
        project_id=request.project_id,
        execution_id=exec_model.execution_id,
        status=request.status,
        executed_cases_count=request.executed_cases_count,
        blocked_cases_count=request.blocked_cases_count,
        unsupported_cases_count=request.unsupported_cases_count,
        cancelled_cases_count=request.cancelled_cases_count,
        error_cases_count=request.error_cases_count,
        halt_reason=request.halt_reason,
    )

    db.commit()

    return ExecutionRecordResponse(
        execution_id=exec_model.execution_id,
        suite_digest=exec_model.suite_digest,
        suite_id=exec_model.suite_id,
        project_id=exec_model.project_id,
        target_mode=exec_model.target_mode,
        caller_identity=exec_model.caller_identity,
        status=ExecutionTrackingStatus(exec_model.status),
        planned_cases_count=exec_model.planned_cases_count,
        executed_cases_count=exec_model.executed_cases_count,
        blocked_cases_count=exec_model.blocked_cases_count,
        unsupported_cases_count=exec_model.unsupported_cases_count,
        cancelled_cases_count=exec_model.cancelled_cases_count,
        error_cases_count=exec_model.error_cases_count,
        halt_reason=exec_model.halt_reason,
        started_at_utc=exec_model.started_at_utc.isoformat(),
        completed_at_utc=exec_model.completed_at_utc.isoformat()
        if exec_model.completed_at_utc
        else None,
        manifest_snapshot=exec_model.manifest_snapshot,
    )


def record_case_execution_progress(
    db: Session,
    project_id: str,
    execution_id: str,
    case_id: str,
    status: str,
    evidence: MatchedPairEvidence | None = None,
) -> None:
    """Record incremental case execution progress and evidence in a short transaction."""
    repo = C3PersistenceRepository(db)
    exec_model = repo.get_execution(project_id, execution_id)
    if not exec_model:
        return

    # Increment counts based on status
    executed = exec_model.executed_cases_count
    blocked = exec_model.blocked_cases_count
    unsupported = exec_model.unsupported_cases_count
    cancelled = exec_model.cancelled_cases_count
    error = exec_model.error_cases_count

    if status == "EXECUTED":
        executed += 1
    elif status == "BLOCKED":
        blocked += 1
    elif status == "UNSUPPORTED":
        unsupported += 1
    elif status == "CANCELLED":
        cancelled += 1
    elif status == "ERROR":
        error += 1

    if evidence:
        repo.save_matched_pair(
            project_id=project_id,
            evidence=evidence,
            execution_id=execution_id,
        )

    repo.update_execution_progress(
        project_id=project_id,
        execution_id=execution_id,
        status=ExecutionTrackingStatus.RUNNING,
        executed_cases_count=executed,
        blocked_cases_count=blocked,
        unsupported_cases_count=unsupported,
        cancelled_cases_count=cancelled,
        error_cases_count=error,
    )
    db.commit()


def finalize_execution_lifecycle(
    db: Session,
    project_id: str,
    execution_id: str,
    summary: SuiteExecutionSummary,
) -> ExecutionRecordResponse:
    """Finalize execution status and progress counts from suite execution summary."""
    repo = C3PersistenceRepository(db)

    # Determine final lifecycle status
    if summary.error_count > 0:
        final_status = ExecutionTrackingStatus.ERROR
    elif summary.halted_early:
        final_status = ExecutionTrackingStatus.CANCELLED
    else:
        final_status = ExecutionTrackingStatus.COMPLETED

    exec_model = repo.update_execution_progress(
        project_id=project_id,
        execution_id=execution_id,
        status=final_status,
        executed_cases_count=summary.executed_count,
        blocked_cases_count=summary.blocked_count,
        unsupported_cases_count=summary.unsupported_count,
        cancelled_cases_count=summary.cancelled_count,
        error_cases_count=summary.error_count,
        halt_reason=summary.halt_reason,
    )
    db.commit()

    return ExecutionRecordResponse(
        execution_id=exec_model.execution_id,
        suite_digest=exec_model.suite_digest,
        suite_id=exec_model.suite_id,
        project_id=exec_model.project_id,
        target_mode=exec_model.target_mode,
        caller_identity=exec_model.caller_identity,
        status=ExecutionTrackingStatus(exec_model.status),
        planned_cases_count=exec_model.planned_cases_count,
        executed_cases_count=exec_model.executed_cases_count,
        blocked_cases_count=exec_model.blocked_cases_count,
        unsupported_cases_count=exec_model.unsupported_cases_count,
        cancelled_cases_count=exec_model.cancelled_cases_count,
        error_cases_count=exec_model.error_cases_count,
        halt_reason=exec_model.halt_reason,
        started_at_utc=exec_model.started_at_utc.isoformat(),
        completed_at_utc=exec_model.completed_at_utc.isoformat()
        if exec_model.completed_at_utc
        else None,
        manifest_snapshot=exec_model.manifest_snapshot,
    )


def get_execution(
    db: Session, project_id: str, execution_id: str
) -> ExecutionRecordResponse | None:
    """Retrieve tracked execution record by execution_id."""
    repo = C3PersistenceRepository(db)
    model = repo.get_execution(project_id, execution_id)
    if not model:
        return None

    return ExecutionRecordResponse(
        execution_id=model.execution_id,
        suite_digest=model.suite_digest,
        suite_id=model.suite_id,
        project_id=model.project_id,
        target_mode=model.target_mode,
        caller_identity=model.caller_identity,
        status=ExecutionTrackingStatus(model.status),
        planned_cases_count=model.planned_cases_count,
        executed_cases_count=model.executed_cases_count,
        blocked_cases_count=model.blocked_cases_count,
        unsupported_cases_count=model.unsupported_cases_count,
        cancelled_cases_count=model.cancelled_cases_count,
        error_cases_count=model.error_cases_count,
        halt_reason=model.halt_reason,
        started_at_utc=model.started_at_utc.isoformat(),
        completed_at_utc=model.completed_at_utc.isoformat()
        if model.completed_at_utc
        else None,
        manifest_snapshot=model.manifest_snapshot,
    )


def list_executions(
    db: Session,
    project_id: str,
    suite_digest: str | None = None,
    status: str | None = None,
    target_mode: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[ExecutionRecordResponse]:
    """List tracked executions with bounded pagination."""
    repo = C3PersistenceRepository(db)
    models, total = repo.list_executions(
        project_id=project_id,
        suite_digest=suite_digest,
        status=status,
        target_mode=target_mode,
        limit=limit,
        offset=offset,
    )

    items = [
        ExecutionRecordResponse(
            execution_id=m.execution_id,
            suite_digest=m.suite_digest,
            suite_id=m.suite_id,
            project_id=m.project_id,
            target_mode=m.target_mode,
            caller_identity=m.caller_identity,
            status=ExecutionTrackingStatus(m.status),
            planned_cases_count=m.planned_cases_count,
            executed_cases_count=m.executed_cases_count,
            blocked_cases_count=m.blocked_cases_count,
            unsupported_cases_count=m.unsupported_cases_count,
            cancelled_cases_count=m.cancelled_cases_count,
            error_cases_count=m.error_cases_count,
            halt_reason=m.halt_reason,
            started_at_utc=m.started_at_utc.isoformat(),
            completed_at_utc=m.completed_at_utc.isoformat()
            if m.completed_at_utc
            else None,
            manifest_snapshot=m.manifest_snapshot,
        )
        for m in models
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


def save_local_fallback_artifact(
    export_dir: Path,
    execution_id: str,
    payload: dict[str, Any],
) -> Path:
    """Save a local sanitized fallback artifact if database writing fails after tool effect.

    Ensures that tool operations are never repeated to recreate evidence.
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_arguments(payload)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = export_dir / f"fallback_{execution_id}_{uuid4().hex[:6]}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)
    return out_path
