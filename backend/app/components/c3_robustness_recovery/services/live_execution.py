"""Live NexaCart suite generation and background execution with C3 persistence.

Component: C3 - Robustness and Failure Recovery Testing

Live trials take about a minute each, so a suite execution is recorded as RUNNING and executed in
the background; the C3 pages poll the execution record. Matched pairs and recovery evaluations are
persisted as each case finishes. Evaluations are computed on the server from the stored evidence
and the C2 facts returned by the C2 bridge, never from client-supplied values.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.generation import (
    FaultGenerationResponse,
    FrozenSuite,
    GenerationPolicy,
    GenerationStatus,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    EvaluationComputeRequest,
    ExecutionCreateRequest,
    ExecutionRecordResponse,
    ExecutionTrackingStatus,
    SuiteRecordResponse,
)
from app.components.c3_robustness_recovery.examples.nexacart_recovery import (
    NEXACART_REFUND_TASK,
    NEXACART_TASKS,
    build_nexacart_generation_request,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    ConflictError,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.nexacart_live import (
    LiveCaseResult,
    NexaCartLiveSuiteRunner,
    task_for_suite,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.run_tracking import (
    create_execution_manifest,
    get_execution,
    record_case_execution_progress,
)
from app.components.c3_robustness_recovery.services.storage import (
    compute_and_store_evaluation,
    store_frozen_suite,
)

logger = logging.getLogger(__name__)

LIVE_TARGET_MODE = "LIVE_AUT"
LIVE_CALLER_IDENTITY = "ACTUAL_AGENT"

# Live jobs run inside this backend process. A RUNNING live execution that is not active here
# (backend restarted, job thread died) can never finish; it is marked INTERRUPTED. Executions owned
# by another backend instance are only interrupted once their heartbeat is older than
# STALE_HEARTBEAT, so a second backend sharing the database is not disturbed.
RUNNER_INSTANCE_ID = f"runner-{uuid4().hex[:12]}"
STALE_HEARTBEAT = timedelta(minutes=10)
_ACTIVE_JOBS: set[str] = set()
_CANCEL_REQUESTS: set[str] = set()
_JOBS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _merge_snapshot(
    db: Session, project_id: str, execution_id: str, **fields: Any
) -> None:
    repo = C3PersistenceRepository(db)
    model = repo.get_execution(project_id, execution_id)
    if model is None:
        return
    snapshot = dict(model.manifest_snapshot or {})
    snapshot.update(fields)
    model.manifest_snapshot = snapshot
    db.commit()


def is_job_active(execution_id: str) -> bool:
    with _JOBS_LOCK:
        return execution_id in _ACTIVE_JOBS


def _interrupt(db: Session, project_id: str, execution_id: str, reason: str) -> None:
    repo = C3PersistenceRepository(db)
    repo.update_execution_progress(
        project_id,
        execution_id,
        ExecutionTrackingStatus.INTERRUPTED,
        halt_reason=reason,
    )
    db.commit()
    _merge_snapshot(db, project_id, execution_id, interrupted_at=_now_iso())


def expire_stale_live_executions(db: Session, project_id: str) -> list[str]:
    """Mark RUNNING live executions that cannot finish as INTERRUPTED. Returns their IDs."""
    repo = C3PersistenceRepository(db)
    models, _ = repo.list_executions(
        project_id=project_id,
        status=ExecutionTrackingStatus.RUNNING.value,
        target_mode=LIVE_TARGET_MODE,
        limit=200,
    )
    now = datetime.now(UTC)
    expired: list[str] = []
    for model in models:
        if is_job_active(model.execution_id):
            continue
        snapshot = model.manifest_snapshot or {}
        owner = snapshot.get("runner_instance")
        heartbeat_raw = snapshot.get("heartbeat_at")
        heartbeat = (
            datetime.fromisoformat(heartbeat_raw)
            if heartbeat_raw
            else model.started_at_utc
        )
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        if owner == RUNNER_INSTANCE_ID:
            reason = "The live job stopped without finishing in this backend process."
        elif now - heartbeat > STALE_HEARTBEAT:
            reason = (
                "No progress for more than "
                f"{int(STALE_HEARTBEAT.total_seconds() // 60)} minutes and the job is not "
                "running in this backend (the backend was probably restarted)."
            )
        else:
            continue
        _interrupt(db, project_id, model.execution_id, reason)
        expired.append(model.execution_id)
    return expired


def request_cancel(
    db: Session, project_id: str, execution_id: str, requested_by: str
) -> ExecutionRecordResponse:
    """Cancel a live execution after its current case, or interrupt it if it is not running."""
    repo = C3PersistenceRepository(db)
    model = repo.get_execution(project_id, execution_id)
    if model is None:
        raise EntityNotFoundError(
            f"Execution '{execution_id}' not found in project '{project_id}'."
        )
    if model.status != ExecutionTrackingStatus.RUNNING.value:
        raise ConflictError(
            f"Execution '{execution_id}' is {model.status}; only RUNNING executions can be cancelled."
        )
    if is_job_active(execution_id):
        with _JOBS_LOCK:
            _CANCEL_REQUESTS.add(execution_id)
        _merge_snapshot(
            db,
            project_id,
            execution_id,
            cancel_requested_at=_now_iso(),
            cancel_requested_by=requested_by,
        )
    else:
        _interrupt(
            db,
            project_id,
            execution_id,
            f"Cancelled by {requested_by}: the job was not running in this backend process "
            "(backend restarted or the job stopped).",
        )
    return get_execution(db, project_id, execution_id)


def generate_and_store_nexacart_suite(
    db: Session,
    project_id: str,
    capabilities: dict[str, Any],
    task_id: str = NEXACART_REFUND_TASK.task_id,
    policy: GenerationPolicy | None = None,
) -> tuple[FaultGenerationResponse, SuiteRecordResponse | None]:
    """Generate feasible cases from NexaCart's live capabilities and persist the frozen suite."""
    task = NEXACART_TASKS[task_id]
    request = build_nexacart_generation_request(project_id, capabilities, task, policy)
    response = generate_feasible_cases(request)
    if (
        response.generation_status != GenerationStatus.GENERATED
        or response.frozen_suite is None
    ):
        return response, None
    return response, store_frozen_suite(db, project_id, response.frozen_suite)


def start_live_execution(
    db: Session,
    project_id: str,
    suite: FrozenSuite,
    suite_digest: str,
    case_ids: list[str],
    agent: dict[str, Any] | None,
    repetitions: int = 1,
) -> ExecutionRecordResponse:
    """Persist a RUNNING live execution manifest before any NexaCart activity."""
    record = create_execution_manifest(
        db,
        project_id,
        ExecutionCreateRequest(
            suite_digest=suite_digest,
            project_id=project_id,
            target_mode=LIVE_TARGET_MODE,
            caller_identity=LIVE_CALLER_IDENTITY,
            planned_cases=[c for c in case_ids for _ in range(repetitions)],
            configuration_snapshot={
                "target": "NexaCart QA harness",
                "adapter_id": suite.adapter_manifest.adapter_id,
                "adapter_version": suite.adapter_manifest.adapter_version,
                "task_id": suite.task_fixture_metadata.task_id,
                "fixture_id": suite.task_fixture_metadata.fixture_id,
                "recovery_contract_id": suite.recovery_contract.contract_id,
                "recovery_contract_version": suite.recovery_contract.contract_version,
                "agent": agent,
                "repetitions": repetitions,
            },
        ),
    )
    repo = C3PersistenceRepository(db)
    repo.update_execution_progress(
        project_id, record.execution_id, ExecutionTrackingStatus.RUNNING
    )
    db.commit()
    # Registered before the background job starts, so it is never seen as stale.
    with _JOBS_LOCK:
        _ACTIVE_JOBS.add(record.execution_id)
    _merge_snapshot(
        db,
        project_id,
        record.execution_id,
        runner_instance=RUNNER_INSTANCE_ID,
        heartbeat_at=_now_iso(),
    )
    return get_execution(db, project_id, record.execution_id) or record


def _append_case_result(
    db: Session, project_id: str, execution_id: str, result: LiveCaseResult
) -> None:
    repo = C3PersistenceRepository(db)
    model = repo.get_execution(project_id, execution_id)
    if model is None:
        return
    snapshot = dict(model.manifest_snapshot or {})
    case_results = list(snapshot.get("case_results") or [])
    evaluation = result.evaluation
    case_results.append(
        {
            "case_id": result.case_id,
            "repetition": result.repetition,
            "status": result.status,
            "pair_id": result.evidence.pair_id if result.evidence else None,
            "exposure_status": result.evidence.exposure_status.value
            if result.evidence
            else None,
            "clean_qualification": result.evidence.clean_qualification.value
            if result.evidence
            else None,
            "recovery_verdict": evaluation.recovery_verdict.value
            if evaluation and evaluation.recovery_verdict
            else None,
            "evaluation_status": evaluation.evaluation_status.value
            if evaluation
            else None,
            "first_violated_rule": evaluation.first_violated_rule
            if evaluation
            else None,
            "reasons": result.reasons,
            "duration_ms": round(result.duration_ms, 1),
        }
    )
    snapshot["case_results"] = case_results
    model.manifest_snapshot = snapshot
    db.commit()


def run_live_execution_job(
    project_id: str,
    execution_id: str,
    suite: FrozenSuite,
    case_ids: list[str],
    session_factory: Callable[[], Session],
    runner: NexaCartLiveSuiteRunner | None = None,
    repetitions: int = 1,
) -> None:
    """Background job: run the live matched pairs and persist progress after every case."""
    db = session_factory()
    repo = C3PersistenceRepository(db)
    counts = {"EXECUTED": 0, "BLOCKED": 0, "UNSUPPORTED": 0, "CANCELLED": 0, "ERROR": 0}
    with _JOBS_LOCK:
        _ACTIVE_JOBS.add(execution_id)

    def is_cancelled() -> bool:
        with _JOBS_LOCK:
            return execution_id in _CANCEL_REQUESTS

    try:
        runner = runner or NexaCartLiveSuiteRunner()
        not_ready = runner.check_suite_readiness(suite)
        if not_ready:
            repo.update_execution_progress(
                project_id,
                execution_id,
                ExecutionTrackingStatus.ERROR,
                blocked_cases_count=len(case_ids) * repetitions,
                halt_reason="Live NexaCart execution BLOCKED: " + " | ".join(not_ready),
            )
            db.commit()
            return

        task = task_for_suite(suite)

        def on_case_done(result: LiveCaseResult) -> None:
            counts[result.status] = counts.get(result.status, 0) + 1
            record_case_execution_progress(
                db,
                project_id,
                execution_id,
                result.case_id,
                result.status,
                evidence=result.evidence,
            )
            if result.evidence is not None and task is not None:
                compute_and_store_evaluation(
                    db,
                    EvaluationComputeRequest(
                        project_id=project_id,
                        pair_id=result.evidence.pair_id,
                        c2_facts=result.c2_facts,
                        pinned_mappings=task.c2_mappings,
                    ),
                )
            _append_case_result(db, project_id, execution_id, result)
            _merge_snapshot(db, project_id, execution_id, heartbeat_at=_now_iso())

        _, halt_reason = runner.run_suite(
            suite,
            project_id=project_id,
            run_id=execution_id,
            case_ids=case_ids,
            on_case_done=on_case_done,
            is_cancelled=is_cancelled,
            repetitions=repetitions,
        )
        if halt_reason and is_cancelled():
            requested_by = (
                repo.get_execution(project_id, execution_id).manifest_snapshot or {}
            ).get("cancel_requested_by", "a user")
            halt_reason = (
                f"Cancelled by {requested_by} after {counts['EXECUTED']} executed case(s); "
                "remaining cases were not run."
            )
        final_status = (
            ExecutionTrackingStatus.ERROR
            if counts["ERROR"]
            else ExecutionTrackingStatus.CANCELLED
            if halt_reason
            else ExecutionTrackingStatus.COMPLETED
        )
        repo.update_execution_progress(
            project_id,
            execution_id,
            final_status,
            executed_cases_count=counts["EXECUTED"],
            blocked_cases_count=counts["BLOCKED"],
            unsupported_cases_count=counts["UNSUPPORTED"],
            cancelled_cases_count=counts["CANCELLED"],
            error_cases_count=counts["ERROR"],
            halt_reason=halt_reason,
        )
        db.commit()
    except Exception as exc:
        logger.exception("Live C3 execution %s failed", execution_id)
        db.rollback()
        try:
            repo.update_execution_progress(
                project_id,
                execution_id,
                ExecutionTrackingStatus.ERROR,
                halt_reason=f"Live execution failed: {type(exc).__name__}: {exc}",
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        with _JOBS_LOCK:
            _ACTIVE_JOBS.discard(execution_id)
            _CANCEL_REQUESTS.discard(execution_id)
        db.close()
