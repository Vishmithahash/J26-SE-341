"""FastAPI router for Shared Projects Workspace endpoints.

Component: Shared Projects Workspace
"""

import math
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
from app.shared.projects.schemas import (
    ConnectionCheckResponse,
    InputReferenceCreateRequest,
    InputReferenceResponse,
    OwnerSummary,
    ProjectCreateRequest,
    ProjectHistoryListResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.shared.projects.service import (
    add_input_reference,
    archive_project,
    check_project_connection,
    create_project,
    disconnect_project,
    get_project,
    list_input_references,
    list_project_history,
    list_projects,
    restore_project,
    update_project,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Shared Projects"])


def _to_project_response(project) -> ProjectResponse:
    """Map Project model to ProjectResponse schema with owner summary and input counts."""
    owner_summary = None
    if project.owner:
        owner_summary = OwnerSummary(
            id=project.owner.id,
            name=project.owner.name,
            email=project.owner.email,
        )

    return ProjectResponse(
        project_id=project.project_id,
        owner_user_id=project.owner_user_id,
        owner=owner_summary,
        name=project.name,
        description=project.description,
        domain=project.domain,
        environment=project.environment,
        backend_base_url=project.backend_base_url,
        backend_health_url=project.backend_health_url,
        agent_endpoint=project.agent_endpoint,
        agent_health_url=project.agent_health_url,
        repository_url=project.repository_url,
        configuration_version=project.configuration_version,
        lifecycle=project.lifecycle,
        connection_state=project.connection_state,
        last_check_timestamp=project.last_check_timestamp,
        last_successful_check_timestamp=project.last_successful_check_timestamp,
        created_at_utc=project.created_at_utc,
        updated_at_utc=project.updated_at_utc,
        input_references_count=len(project.input_references) if project.input_references else 0,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new target application project",
)
def create_new_project(
    data: ProjectCreateRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Register an application with backend and optional agent connection endpoints."""
    project = create_project(db, current_user, data)
    return _to_project_response(project)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List registered projects",
)
def get_projects(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None),
    connection_state: str | None = Query(default=None),
    lifecycle: str | None = Query(default=None),
):
    """Retrieve paginated projects scoped to the authenticated user (or all projects for ADMIN)."""
    if limit is not None:
        effective_page_size = limit
        effective_offset = offset if offset is not None else 0
        effective_page = (effective_offset // effective_page_size) + 1
    else:
        effective_page_size = page_size
        effective_page = page

    items, total = list_projects(
        db=db,
        user=current_user,
        page=effective_page,
        page_size=effective_page_size,
        search=search,
        connection_state=connection_state,
        lifecycle=lifecycle,
    )
    pages = math.ceil(total / effective_page_size) if total > 0 else 1
    return ProjectListResponse(
        items=[_to_project_response(p) for p in items],
        total=total,
        page=effective_page,
        page_size=effective_page_size,
        pages=pages,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Retrieve project details",
)
def get_single_project(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get project configuration, lifecycle, and current connection status."""
    project = get_project(db, current_user, project_id)
    return _to_project_response(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project details or connection configuration",
)
def update_existing_project(
    project_id: str,
    data: ProjectUpdateRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update metadata or URLs. Changing connection URLs resets connection state to NOT_CHECKED."""
    project = update_project(db, current_user, project_id, data)
    return _to_project_response(project)


@router.post(
    "/{project_id}/check-connection",
    response_model=ConnectionCheckResponse,
    summary="Probe documented health endpoints",
)
async def check_connection(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Execute a non-mutating HTTP GET health probe against configured health endpoints."""
    return await check_project_connection(db, current_user, project_id)


@router.post(
    "/{project_id}/disconnect",
    response_model=ProjectResponse,
    summary="Disconnect registered project",
)
def disconnect(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Set project connection state to DISCONNECTED without modifying the target application."""
    project = disconnect_project(db, current_user, project_id)
    return _to_project_response(project)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project record",
)
def archive(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Archive a project record, preserving its configuration and audit history."""
    project = archive_project(db, current_user, project_id)
    return _to_project_response(project)


@router.post(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    summary="Restore an archived project",
)
def restore(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Restore an archived project to active status."""
    project = restore_project(db, current_user, project_id)
    return _to_project_response(project)


@router.get(
    "/{project_id}/history",
    response_model=ProjectHistoryListResponse,
    summary="Retrieve audit history events",
)
def get_history(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    """Get paginated history and connection transition events for this project."""
    items, total = list_project_history(
        db=db,
        user=current_user,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )
    return ProjectHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{project_id}/inputs",
    response_model=list[InputReferenceResponse],
    summary="List registered input references",
)
def get_inputs(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve all registered input specifications, documentation, and schema references."""
    return list_input_references(db, current_user, project_id)


@router.post(
    "/{project_id}/inputs",
    response_model=InputReferenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new input reference",
)
def add_input(
    project_id: str,
    data: InputReferenceCreateRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Register a new input reference, preserving historical versions."""
    return add_input_reference(db, current_user, project_id, data)
