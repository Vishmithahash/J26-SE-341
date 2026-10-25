"""Live NexaCart endpoints for Component 3: readiness, automatic suite generation, execution.

Component: C3 - Robustness and Failure Recovery Testing
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.api.authorization import (
    require_c3_active_user,
    verify_c3_project_access,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    GenerationPolicy,
)
from app.components.c3_robustness_recovery.contracts.live import (
    LiveExecutionRequest,
    LiveExecutionStartResponse,
    LiveSuiteGenerationRequest,
    LiveSuiteGenerationResponse,
    LiveTargetReadinessResponse,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionRecordResponse,
    PaginatedResponse,
)
from app.components.c3_robustness_recovery.examples.nexacart_recovery import (
    NEXACART_ADAPTER_ID,
    NEXACART_TASKS,
    build_nexacart_adapter_manifest,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    ConflictError,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.nexacart_live import (
    NexaCartLiveSuiteRunner,
)
from app.components.c3_robustness_recovery.services.live_execution import (
    LIVE_TARGET_MODE,
    expire_stale_live_executions,
    generate_and_store_nexacart_suite,
    request_cancel,
    run_live_execution_job,
    start_live_execution,
)
from app.components.c3_robustness_recovery.services.recovery_cost import (
    project_recovery_cost,
)
from app.components.c3_robustness_recovery.services.run_tracking import (
    list_executions as service_list_executions,
)
from app.components.c3_robustness_recovery.services.storage import (
    get_suite as service_get_suite,
)
from app.database import SessionLocal, get_db
from app.shared.auth.models import User
from app.shared.integration.adapters import LiveNexaCartTargetAdapter

router = APIRouter(prefix="/live/nexacart")


def get_c3_live_target() -> LiveNexaCartTargetAdapter:
    """Live NexaCart target adapter (overridden in hermetic tests)."""
    return LiveNexaCartTargetAdapter()


def get_c3_session_factory() -> Callable[[], Session]:
    """Session factory for background live executions (overridden in hermetic tests)."""
    return SessionLocal


def _load_capabilities(target: LiveNexaCartTargetAdapter) -> dict:
    ready, reasons = target.check_readiness()
    if ready.value != "READY":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live NexaCart target is BLOCKED: " + " | ".join(reasons),
        )
    return target.client.get_capabilities()


@router.get(
    "/readiness",
    response_model=LiveTargetReadinessResponse,
    summary="Check Live NexaCart Harness Readiness",
    description=(
        "Checks NexaCart health, QA admin credentials and the external QA harness, and returns "
        "the C3 capability manifest built from the harness. Creates no NexaCart data."
    ),
)
def live_readiness(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Annotated[LiveNexaCartTargetAdapter, Depends(get_c3_live_target)],
) -> LiveTargetReadinessResponse:
    verify_c3_project_access(project_id, current_user, db)
    tasks = [
        {
            "task_id": t.task_id,
            "task_version": t.task_version,
            "instruction": t.instruction,
            "fixture_id": t.fixture_id,
            "target_tool_ids": t.target_tool_ids,
            "recovery_contract_id": t.recovery_contract.contract_id,
            "recovery_contract_version": t.recovery_contract.contract_version,
        }
        for t in NEXACART_TASKS.values()
    ]
    ready, reasons = target.check_readiness()
    if ready.value != "READY":
        return LiveTargetReadinessResponse(
            ready=False, reasons=reasons, base_url=target.base_url, tasks=tasks
        )
    try:
        capabilities = target.client.get_capabilities()
    except Exception as exc:  # noqa: BLE001
        return LiveTargetReadinessResponse(
            ready=False,
            reasons=[f"NexaCart harness capabilities unavailable: {exc}"],
            base_url=target.base_url,
            tasks=tasks,
        )
    manifest = build_nexacart_adapter_manifest(capabilities)
    return LiveTargetReadinessResponse(
        ready=True,
        base_url=target.base_url,
        harness_version=manifest.adapter_version,
        agent=capabilities.get("agent"),
        tools=[
            {"tool_id": t.tool_id, "mutability": t.mutability.value}
            for t in manifest.tools
        ],
        supported_combinations_count=len(manifest.supported_combinations),
        tasks=tasks,
    )


@router.post(
    "/suites/generate",
    response_model=LiveSuiteGenerationResponse,
    summary="Generate and Store a NexaCart Fault Suite",
    description=(
        "Builds the adapter capability manifest from NexaCart's live harness capabilities, "
        "automatically generates and validates feasible fault cases for the registered NexaCart "
        "task, freezes the suite and stores it in the project. No agent run is started."
    ),
)
def generate_live_suite(
    request: LiveSuiteGenerationRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Annotated[LiveNexaCartTargetAdapter, Depends(get_c3_live_target)],
) -> LiveSuiteGenerationResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    task = NEXACART_TASKS.get(request.task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered NexaCart task '{request.task_id}'.",
        )
    capabilities = _load_capabilities(target)
    policy = GenerationPolicy(
        max_cases=request.max_cases,
        seed=request.seed,
        target_tool_ids=request.target_tool_ids or task.target_tool_ids,
        target_fault_families=request.target_fault_families,
        target_effect_phases=request.target_effect_phases,
        coverage_strategy="TOOL_FAMILY_PHASE",
    )
    try:
        generation, stored = generate_and_store_nexacart_suite(
            db, request.project_id, capabilities, task.task_id, policy
        )
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc
    return LiveSuiteGenerationResponse(generation=generation, stored_suite=stored)


@router.post(
    "/executions",
    response_model=LiveExecutionStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run a Stored NexaCart Suite Live",
    description=(
        "Starts a background execution: every selected case runs as a clean and a fault trial on "
        "fresh NexaCart fixtures with NexaCart's own LLM agent. Poll GET /executions/{id} for "
        "progress; pairs and recovery evaluations are stored as each case finishes."
    ),
)
def start_live_suite_execution(
    request: LiveExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Annotated[LiveNexaCartTargetAdapter, Depends(get_c3_live_target)],
    session_factory: Annotated[Callable[[], Session], Depends(get_c3_session_factory)],
) -> LiveExecutionStartResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    suite_record = service_get_suite(db, request.project_id, request.suite_id_or_digest)
    if not suite_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite '{request.suite_id_or_digest}' not found in project '{request.project_id}'.",
        )
    suite = suite_record.frozen_suite
    if suite.adapter_manifest.adapter_id != NEXACART_ADAPTER_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Suite adapter '{suite.adapter_manifest.adapter_id}' cannot run live. Generate a suite "
                "from the NexaCart harness capabilities first."
            ),
        )
    suite_case_ids = [c.case_id for c in suite.selected_cases]
    unknown = [c for c in request.case_ids or [] if c not in suite_case_ids]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cases not in suite: {unknown}",
        )
    case_ids = [
        c for c in suite_case_ids if not request.case_ids or c in request.case_ids
    ]

    # Fail fast (no execution record) when NexaCart cannot be reached.
    capabilities = _load_capabilities(target)
    try:
        execution = start_live_execution(
            db,
            request.project_id,
            suite,
            suite_record.suite_digest,
            case_ids,
            agent=capabilities.get("agent"),
            repetitions=request.repetitions,
        )
    except (ConflictError, EntityNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    background_tasks.add_task(
        run_live_execution_job,
        request.project_id,
        execution.execution_id,
        suite,
        case_ids,
        session_factory,
        NexaCartLiveSuiteRunner(
            adapter=target,
            max_suite_duration_sec=request.max_suite_duration_sec * request.repetitions,
        ),
        request.repetitions,
    )
    return LiveExecutionStartResponse(
        execution=execution,
        planned_case_ids=[c for c in case_ids for _ in range(request.repetitions)],
        note=(
            "Live execution started. Each case runs a clean and a fault agent trial on NexaCart "
            "(about 1-3 minutes per case with local Ollama)."
        ),
    )


@router.get(
    "/executions",
    response_model=PaginatedResponse[ExecutionRecordResponse],
    summary="List Live NexaCart Executions",
    description=(
        "Lists live executions of the project, newest first. RUNNING executions that can no longer "
        "finish (backend restarted, job stopped) are marked INTERRUPTED first."
    ),
)
def list_live_executions(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> PaginatedResponse[ExecutionRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    expire_stale_live_executions(db, project_id)
    return service_list_executions(
        db, project_id=project_id, target_mode=LIVE_TARGET_MODE, limit=limit
    )


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutionRecordResponse,
    summary="Cancel a Live NexaCart Execution",
    description=(
        "Stops a running live execution after the case in progress (an agent run cannot be "
        "interrupted midway). An execution that is no longer running in this backend is marked "
        "INTERRUPTED immediately."
    ),
)
def cancel_live_execution(
    execution_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutionRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return request_cancel(db, project_id, execution_id, current_user.email)
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get(
    "/recovery-cost",
    summary="Recovery Cost of Live Matched Pairs",
    description=(
        "Extra time, tool calls, retries and tokens of each live fault trial compared with its "
        "clean control, with averages per fault family and effect phase (proposal RQ4)."
    ),
)
def live_recovery_cost(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    execution_id: str | None = None,
) -> dict:
    verify_c3_project_access(project_id, current_user, db)
    return project_recovery_cost(db, project_id, execution_id)
