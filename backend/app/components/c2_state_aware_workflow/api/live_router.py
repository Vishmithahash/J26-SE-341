"""Live NexaCart endpoints for Component 2: readiness, reference workflows, live executions.

Component: C2 - State-Aware Multi-Step Workflow Testing

Mounted inside the C2 router, so every route is project-scoped and authorised by
``authorize_c2_project_access``.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
    NEXACART_WORKFLOWS,
)
from app.components.c2_state_aware_workflow.integrations.live_execution import (
    execution_to_dict,
    import_reference_model,
    list_reference_workflows,
    run_live_execution_job,
    start_live_execution,
)
from app.components.c2_state_aware_workflow.integrations.nexacart_live import (
    NexaCartLiveWorkflowRunner,
)
from app.components.c2_state_aware_workflow.persistence.models import C2LiveExecution
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.database import SessionLocal, get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
from app.shared.integration.adapters import LiveNexaCartTargetAdapter

router = APIRouter(prefix="/projects/{project_id}/live/nexacart")


class LiveExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., min_length=1)
    test_ids: list[str] | None = Field(
        None, description="Cases to run (all suite cases when omitted)."
    )
    max_suite_duration_sec: float = Field(3600.0, gt=0, le=6 * 3600)


def get_c2_live_target() -> LiveNexaCartTargetAdapter:
    """Live NexaCart target adapter (overridden in hermetic tests)."""
    return LiveNexaCartTargetAdapter()


def get_c2_session_factory() -> Callable[[], Session]:
    """Session factory for background live executions (overridden in hermetic tests)."""
    return SessionLocal


def _target_capabilities(
    target: LiveNexaCartTargetAdapter,
) -> tuple[bool, list[str], dict]:
    ready, reasons = target.check_readiness()
    if ready.value != "READY":
        return False, reasons, {}
    try:
        return True, [], target.client.get_capabilities()
    except Exception as exc:  # noqa: BLE001
        return False, [f"NexaCart harness capabilities unavailable: {exc}"], {}


@router.get("/readiness", summary="Check Live NexaCart Readiness for C2")
def live_readiness(
    project_id: str,
    target: Annotated[LiveNexaCartTargetAdapter, Depends(get_c2_live_target)],
) -> dict[str, Any]:
    """NexaCart health, QA admin credentials and harness capabilities. Creates no data."""
    ready, reasons, capabilities = _target_capabilities(target)
    return {
        "ready": ready,
        "reasons": reasons,
        "base_url": target.base_url,
        "harness_version": capabilities.get("harnessVersion"),
        "agent": capabilities.get("agent"),
        "tools": [
            {"name": t.get("name"), "is_state_changing": bool(t.get("isStateChanging"))}
            for t in capabilities.get("tools", [])
        ],
        "observation": capabilities.get("observation"),
    }


@router.get("/workflows", summary="List NexaCart Reference Workflows")
def reference_workflows(
    project_id: str, db: Annotated[Session, Depends(get_db)]
) -> list[dict[str, Any]]:
    """NexaCart reference EFSMs with their import, approval and suite status in this project."""
    return list_reference_workflows(db, project_id)


@router.post(
    "/workflows/{model_id}/import",
    status_code=status.HTTP_201_CREATED,
    summary="Import a NexaCart Reference EFSM as a Draft",
)
def import_workflow(
    project_id: str, model_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    """Create the reference EFSM as a DRAFT. Validate and approve it on the Models tab."""
    if model_id not in NEXACART_WORKFLOWS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No NexaCart reference workflow '{model_id}'.",
        )
    return {"model_id": model_id, **import_reference_model(db, project_id, model_id)}


@router.post(
    "/executions",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run Generated C2 Cases Live on NexaCart",
)
def start_execution(
    project_id: str,
    request: LiveExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Annotated[LiveNexaCartTargetAdapter, Depends(get_c2_live_target)],
    session_factory: Annotated[Callable[[], Session], Depends(get_c2_session_factory)],
) -> dict[str, Any]:
    """Starts a background execution; poll GET /executions/{execution_id} for progress."""
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, request.suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{request.suite_id}' not found for project '{project_id}'.",
        )
    if suite.model_id not in NEXACART_WORKFLOWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Suite model '{suite.model_id}' has no NexaCart fixture binding. Generate a suite "
                "from an approved NexaCart reference workflow."
            ),
        )
    suite_ids = [c.test_id for c in repo.list_test_cases(project_id, suite.suite_id)]
    unknown = [t for t in request.test_ids or [] if t not in suite_ids]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cases not in suite: {unknown}",
        )
    test_ids = [t for t in suite_ids if not request.test_ids or t in request.test_ids]

    # Fail fast (no execution record) when NexaCart cannot be reached.
    ready, reasons, capabilities = _target_capabilities(target)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live NexaCart target is BLOCKED: " + " | ".join(reasons),
        )
    record = start_live_execution(
        db,
        project_id,
        suite,
        test_ids,
        user_id=str(current_user.id),
        capabilities=capabilities,
        base_url=target.base_url,
    )
    background_tasks.add_task(
        run_live_execution_job,
        project_id,
        record.execution_id,
        session_factory,
        NexaCartLiveWorkflowRunner(
            adapter=target, max_suite_duration_sec=request.max_suite_duration_sec
        ),
    )
    return {
        **execution_to_dict(record),
        "note": (
            "Live execution started. Each live case is one NexaCart agent run on a fresh fixture "
            "(about 1-2 minutes with local Ollama); mutants reuse their parent's live trace."
        ),
    }


@router.get("/executions", summary="List Live C2 Executions")
def list_executions(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    suite_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    stmt = select(C2LiveExecution).where(C2LiveExecution.project_id == project_id)
    if suite_id:
        stmt = stmt.where(C2LiveExecution.suite_id == suite_id)
    rows = db.execute(stmt.order_by(C2LiveExecution.created_at.desc())).scalars().all()
    return [execution_to_dict(r) for r in rows]


@router.get("/executions/{execution_id}", summary="Get a Live C2 Execution")
def get_execution(
    project_id: str, execution_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    record = db.get(C2LiveExecution, execution_id)
    if record is None or record.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live execution '{execution_id}' not found in project '{project_id}'.",
        )
    return execution_to_dict(record)
