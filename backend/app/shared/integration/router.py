"""FastAPI REST routes for Shared Cross-Component Integration and Run Plans.

Component: Shared Integration Foundation (Part 1)
Enforces:
- Authenticated platform access via require_active_user.
- Strict project scoping and safe authorization via get_project.
- Prevention of cross-project references.
- Retrieval and creation of frozen run plans.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
from app.shared.integration.contracts import (
    ComponentReferencesPlan,
    IntegrationPlanListResponse,
    IntegrationReadinessReport,
    IntegrationRunPlanCreateRequest,
    IntegrationRunPlanResponse,
    ReadinessCheckRequest,
)
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
