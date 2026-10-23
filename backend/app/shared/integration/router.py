"""FastAPI REST routes for Shared Cross-Component Integration and Run Plans.

Component: Shared Integration Foundation (Part 1)
Enforces:
- Authenticated platform access via require_active_user.
- Strict project scoping and safe authorization via get_project.
- Prevention of cross-project references.
- Retrieval and creation of frozen run plans.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
from app.shared.integration.contracts import (
    CombinedQAReport,
    ComponentReferencesPlan,
    ExecutionListResponse,
    ExecutionStartRequest,
    ExecutionStatusResponse,
    IntegrationPlanListResponse,
    IntegrationReadinessReport,
    IntegrationReportListResponse,
    IntegrationRunPlanCreateRequest,
    IntegrationRunPlanResponse,
    ReadinessCheckRequest,
    ReplayComparisonResponse,
)
from app.shared.integration.executor import SharedExecutionCoordinator
from app.shared.integration.replay import EvidenceReplayService
from app.shared.integration.reporting import SharedReportAggregator
from app.shared.integration.service import IntegrationService
from app.shared.projects.models import Project
from app.shared.projects.service import get_project

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/integration",
    tags=["Shared: Cross-Component Integration"],
)


def get_authorized_project(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Project:
    """Validate authenticated caller role and verify project authorization.

    Fails closed with HTTP 404 if project is missing or owned by another user.
    """
    return get_project(db, current_user, project_id)


@router.post(
    "/plans",
    response_model=IntegrationRunPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and freeze a shared integration run plan",
    description=(
        "Registers a new integration run plan referencing validated component inputs. "
        "Evaluates cross-component readiness, freezes model/suite/contract digests, "
        "and maps native entity identifiers to a shared integration run ID. "
        "Does not launch runtime executions."
    ),
)
def create_integration_plan(
    project_id: str,
    payload: IntegrationRunPlanCreateRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[Project, Depends(get_authorized_project)],
) -> IntegrationRunPlanResponse:
    """Create and freeze a new integration run plan."""
    service = IntegrationService(db)
    return service.create_run_plan(project, current_user, payload)


@router.get(
    "/plans",
    response_model=IntegrationPlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="List integration run plans for a project",
    description="Returns a paginated list of registered integration run plans scoped to the authorized project.",
)
def list_integration_plans(
    project_id: str,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> IntegrationPlanListResponse:
    """List integration run plans for the authorized project."""
    service = IntegrationService(db)
    return service.list_run_plans(project, page=page, page_size=page_size)


@router.get(
    "/plans/{plan_id}",
    response_model=IntegrationRunPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an integration run plan by ID",
    description="Fetches an integration run plan by its primary UUID or integration_run_id.",
)
def get_integration_plan(
    project_id: str,
    plan_id: str,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationRunPlanResponse:
    """Retrieve an integration run plan by plan_id or integration_run_id."""
    service = IntegrationService(db)
    return service.get_run_plan(project, plan_id)


@router.post(
    "/plans/validate-readiness",
    response_model=IntegrationReadinessReport,
    status_code=status.HTTP_200_OK,
    summary="Validate integration readiness for candidate component references",
    description=(
        "Performs ad-hoc deterministic readiness evaluation for candidate component references "
        "without persisting a run plan. Detects unapproved models, unfrozen suites, and missing configs."
    ),
)
def validate_readiness(
    project_id: str,
    payload: ReadinessCheckRequest,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationReadinessReport:
    """Validate readiness for candidate component references."""
    service = IntegrationService(db)
    references = ComponentReferencesPlan(
        c1=payload.c1_reference,
        c2=payload.c2_reference,
        c3=payload.c3_reference,
        c4=payload.c4_reference,
    )
    return service.check_readiness(project_id, references)


@router.post(
    "/plans/{plan_id}/execute",
    response_model=ExecutionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a frozen integration run plan",
    description=(
        "Launches coordinated execution of the validated run plan. "
        "Executes the application once per trial, captures retained evidence, "
        "and evaluates the evidence using C1, C2, C3, and C4 evaluators."
    ),
)
def execute_plan(
    project_id: str,
    plan_id: str,
    payload: ExecutionStartRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[Project, Depends(get_authorized_project)],
) -> ExecutionStatusResponse:
    """Execute a validated integration run plan."""
    coordinator = SharedExecutionCoordinator(db)
    return coordinator.execute_plan(project, current_user, plan_id, payload)


@router.get(
    "/plans/{plan_id}/executions",
    response_model=ExecutionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List executions for an integration run plan",
    description="Returns all executions and evaluations performed for this plan.",
)
def list_executions(
    project_id: str,
    plan_id: str,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutionListResponse:
    """List executions for a plan."""
    coordinator = SharedExecutionCoordinator(db)
    return coordinator.list_executions(project, plan_id)


@router.get(
    "/plans/{plan_id}/executions/{execution_id}",
    response_model=ExecutionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get execution status and evaluation results",
    description="Retrieves execution status, retained evidence digest, and component evaluations.",
)
def get_execution(
    project_id: str,
    plan_id: str,
    execution_id: str,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutionStatusResponse:
    """Retrieve execution status and findings."""
    coordinator = SharedExecutionCoordinator(db)
    return coordinator.get_execution(project, plan_id, execution_id)


@router.post(
    "/plans/{plan_id}/executions/{execution_id}/cancel",
    response_model=ExecutionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an ongoing execution",
    description="Safely requests execution cancellation with bounded settling.",
)
def cancel_execution(
    project_id: str,
    plan_id: str,
    execution_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[Project, Depends(get_authorized_project)],
) -> ExecutionStatusResponse:
    """Cancel an active execution."""
    coordinator = SharedExecutionCoordinator(db)
    return coordinator.cancel_execution(project, plan_id, execution_id)


@router.get(
    "/plans/{plan_id}/executions/{execution_id}/report",
    response_model=CombinedQAReport,
    status_code=status.HTTP_200_OK,
    summary="Retrieve or generate a combined cross-component QA report",
    description=(
        "Consumes persisted component findings and verdicts for the execution. "
        "Links related findings across shared events/entities without collapsing distinct defects. "
        "Deduplicates repeated publications using stable hashes."
    ),
)
def get_combined_report(
    project_id: str,
    plan_id: str,
    execution_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[Project, Depends(get_authorized_project)],
) -> CombinedQAReport:
    """Retrieve or generate combined QA report."""
    aggregator = SharedReportAggregator(db)
    return aggregator.generate_report(
        project, execution_id, user=current_user, persist=True
    )


@router.get(
    "/plans/{plan_id}/executions/{execution_id}/report/export",
    status_code=status.HTTP_200_OK,
    summary="Export combined QA report as JSON or CSV",
    description="Exports the combined QA report in formatted JSON or structured CSV format.",
)
def export_combined_report(
    project_id: str,
    plan_id: str,
    execution_id: str,
    format: str = Query(
        default="json", pattern="^(json|csv)$", description="Export format"
    ),
    current_user: Annotated[User, Depends(require_active_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
    project: Annotated[Project, Depends(get_authorized_project)] = None,
) -> Response:
    """Export combined QA report."""
    aggregator = SharedReportAggregator(db)
    report = aggregator.generate_report(
        project, execution_id, user=current_user, persist=False
    )
    if format == "csv":
        csv_data = aggregator.export_report_csv(report)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="report_{execution_id}.csv"'
            },
        )
    else:
        json_data = aggregator.export_report_json(report)
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="report_{execution_id}.json"'
            },
        )


@router.post(
    "/plans/{plan_id}/executions/{execution_id}/replay",
    response_model=ReplayComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Replay evaluation from retained evidence without target execution",
    description=(
        "Replays stored execution evidence through pinned component evaluators. "
        "Strictly verifies deterministic semantic equality without re-executing target services."
    ),
)
def replay_evaluation(
    project_id: str,
    plan_id: str,
    execution_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[Project, Depends(get_authorized_project)],
) -> ReplayComparisonResponse:
    """Replay retained evidence evaluation."""
    replay_service = EvidenceReplayService(db)
    return replay_service.replay_execution(project, current_user, execution_id)


@router.get(
    "/reports",
    response_model=IntegrationReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List published combined QA reports for a project",
    description="Returns a paginated list of published combined QA reports with optional component, verdict, and execution mode filters.",
)
def list_reports(
    project_id: str,
    project: Annotated[Project, Depends(get_authorized_project)],
    db: Annotated[Session, Depends(get_db)],
    component: str | None = Query(default=None, description="Filter by component"),
    verdict: str | None = Query(default=None, description="Filter by overall verdict"),
    execution_mode: str | None = Query(
        default=None, description="Filter by target mode"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> IntegrationReportListResponse:
    """List combined reports for project."""
    aggregator = SharedReportAggregator(db)
    return aggregator.list_reports(
        project=project,
        component=component,
        verdict=verdict,
        execution_mode=execution_mode,
        page=page,
        page_size=page_size,
    )
