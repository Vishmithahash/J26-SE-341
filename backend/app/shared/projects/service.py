"""Business logic, authorization rules, and persistence for Shared Projects.

Component: Shared Projects Workspace
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.shared.auth.models import User, UserRole
from app.shared.projects.connection_service import (
    evaluate_connection_state,
    probe_endpoint,
)
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectHistoryEvent,
    ProjectHistoryEventType,
    ProjectInputReference,
    ProjectLifecycle,
    generate_id,
    generate_project_id,
)
from app.shared.projects.schemas import (
    ConnectionCheckResponse,
    InputReferenceCreateRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
)


def _assert_access(project: Project, user: User) -> None:
    """Ensure that the authenticated user possesses access to the project.

    ADMIN has access to all projects.
    USER has access only to their own projects.
    Fails closed with 404 to prevent identifier enumeration.
    """
    if user.role != UserRole.ADMIN and project.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )


def _record_event(
    db: Session,
    project_id: str,
    user: User,
    event_type: ProjectHistoryEventType,
    config_version: int,
    previous_state: dict[str, Any] | None = None,
    resulting_state: dict[str, Any] | None = None,
    safe_details: dict[str, Any] | None = None,
) -> ProjectHistoryEvent:
    """Append a non-destructible event to the project's audit history."""
    event = ProjectHistoryEvent(
        event_id=generate_id("evt"),
        project_id=project_id,
        acting_account_id=user.id,
        acting_account_email=user.email,
        timestamp_utc=datetime.now(UTC),
        configuration_version=config_version,
        event_type=event_type.value,
        previous_state=previous_state,
        resulting_state=resulting_state,
        safe_details=safe_details,
    )
    db.add(event)
    return event


def create_project(db: Session, user: User, data: ProjectCreateRequest) -> Project:
    """Register a new application project with ownership bound to the authenticated account."""
    new_project_id = generate_project_id(data.name)

    project = Project(
        project_id=new_project_id,
        owner_user_id=user.id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        domain=data.domain,
        environment=data.environment,
        backend_base_url=data.backend_base_url.strip(),
        backend_health_url=data.backend_health_url.strip(),
        agent_endpoint=data.agent_endpoint.strip() if data.agent_endpoint else None,
        agent_health_url=data.agent_health_url.strip() if data.agent_health_url else None,
        repository_url=data.repository_url.strip() if data.repository_url else None,
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.NOT_CHECKED.value,
    )
    db.add(project)

    # Initial input references if provided
    for inp in data.initial_inputs:
        ref = ProjectInputReference(
            reference_id=generate_id("ref"),
            project_id=new_project_id,
            category=inp.category,
            label=inp.label,
            reference_location=inp.reference_location,
            version=inp.version,
            registered_at_utc=datetime.now(UTC),
        )
        db.add(ref)

    _record_event(
        db=db,
        project_id=new_project_id,
        user=user,
        event_type=ProjectHistoryEventType.PROJECT_CREATED,
        config_version=1,
        previous_state=None,
        resulting_state={
            "lifecycle": project.lifecycle,
            "connection_state": project.connection_state,
        },
        safe_details={"name": project.name, "domain": project.domain},
    )

    db.commit()
    db.refresh(project)
    return project


def list_projects(
    db: Session,
    user: User,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    connection_state: str | None = None,
    lifecycle: str | None = None,
) -> tuple[list[Project], int]:
    """List projects filtered by user ownership and query filters."""
    query = select(Project)

    # Scoping: USER sees only own projects, ADMIN sees all
    if user.role != UserRole.ADMIN:
        query = query.where(Project.owner_user_id == user.id)

    # Lifecycle filter
    if lifecycle:
        query = query.where(Project.lifecycle == lifecycle)

    # Connection state filter
    if connection_state:
        query = query.where(Project.connection_state == connection_state)

    # Search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Project.name.ilike(term),
                Project.description.ilike(term),
                Project.domain.ilike(term),
                Project.project_id.ilike(term),
            )
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Pagination & sorting
    offset = max(0, (page - 1) * page_size)
    query = query.order_by(desc(Project.updated_at_utc)).offset(offset).limit(page_size)

    items = db.scalars(query).all()
    return list(items), total


def get_project(db: Session, user: User, project_id: str) -> Project:
    """Retrieve project by ID, strictly enforcing authorization."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    _assert_access(project, user)
    return project


def update_project(
    db: Session,
    user: User,
    project_id: str,
    data: ProjectUpdateRequest,
) -> Project:
    """Update project metadata or connection URLs, checking concurrency and versioning."""
    project = get_project(db, user, project_id)

    if project.lifecycle == ProjectLifecycle.ARCHIVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit an archived project. Please restore it first.",
        )

    # Concurrency check
    if data.expected_version is not None and data.expected_version != project.configuration_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Configuration version conflict: current is {project.configuration_version}, "
                f"expected {data.expected_version}. Please reload and reapply."
            ),
        )

    prev_state = {
        "lifecycle": project.lifecycle,
        "connection_state": project.connection_state,
        "configuration_version": project.configuration_version,
    }

    url_fields_changed = False
    details_changed = False

    # Check connection setting alterations
    if data.backend_base_url and data.backend_base_url.strip() != project.backend_base_url:
        project.backend_base_url = data.backend_base_url.strip()
        url_fields_changed = True

    if data.backend_health_url and data.backend_health_url.strip() != project.backend_health_url:
        project.backend_health_url = data.backend_health_url.strip()
        url_fields_changed = True

    if data.agent_endpoint is not None:
        new_val = data.agent_endpoint.strip() if data.agent_endpoint.strip() else None
        if new_val != project.agent_endpoint:
            project.agent_endpoint = new_val
            url_fields_changed = True

    if data.agent_health_url is not None:
        new_val = data.agent_health_url.strip() if data.agent_health_url.strip() else None
        if new_val != project.agent_health_url:
            project.agent_health_url = new_val
            url_fields_changed = True

    # Check other details
    if data.name and data.name.strip() != project.name:
        project.name = data.name.strip()
        details_changed = True

    if data.description is not None:
        new_desc = data.description.strip() if data.description.strip() else None
        if new_desc != project.description:
            project.description = new_desc
            details_changed = True

    if data.domain and data.domain != project.domain:
        project.domain = data.domain
        details_changed = True

    if data.environment and data.environment != project.environment:
        project.environment = data.environment
        details_changed = True

    if data.repository_url is not None:
        new_repo = data.repository_url.strip() if data.repository_url.strip() else None
        if new_repo != project.repository_url:
            project.repository_url = new_repo
            details_changed = True

    if url_fields_changed or details_changed:
        project.configuration_version += 1
        project.updated_at_utc = datetime.now(UTC)

        event_type = (
            ProjectHistoryEventType.CONNECTION_SETTINGS_UPDATED
            if url_fields_changed
            else ProjectHistoryEventType.PROJECT_UPDATED
        )

        if url_fields_changed:
            # Editing connection settings immediately invalidates previous connection status
            project.connection_state = ProjectConnectionState.NOT_CHECKED.value

        _record_event(
            db=db,
            project_id=project.project_id,
            user=user,
            event_type=event_type,
            config_version=project.configuration_version,
            previous_state=prev_state,
            resulting_state={
                "lifecycle": project.lifecycle,
                "connection_state": project.connection_state,
                "configuration_version": project.configuration_version,
            },
            safe_details={"url_settings_changed": url_fields_changed},
        )

        db.commit()
        db.refresh(project)

    return project


async def check_project_connection(
    db: Session,
    user: User,
    project_id: str,
) -> ConnectionCheckResponse:
    """Run an isolated connection verification check on the project's health endpoints."""
    project = get_project(db, user, project_id)

    if project.lifecycle == ProjectLifecycle.ARCHIVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot perform a connection check on an archived project. Please restore it first.",
        )

    checked_version = project.configuration_version
    checked_at = datetime.now(UTC)

    # 1. Probe endpoints asynchronously
    backend_outcome = await probe_endpoint(project.backend_health_url)
    agent_outcome = await probe_endpoint(project.agent_health_url)

    new_state, summary = evaluate_connection_state(backend_outcome, agent_outcome)

    # 2. Re-fetch project to check against in-flight concurrency
    db.expire_all()
    current_project = db.get(Project, project_id)
    if not current_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project was removed.")

    prev_state = {
        "lifecycle": current_project.lifecycle,
        "connection_state": current_project.connection_state,
        "configuration_version": current_project.configuration_version,
    }

    _record_event(
        db=db,
        project_id=project_id,
        user=user,
        event_type=ProjectHistoryEventType.CONNECTION_CHECKED,
        config_version=checked_version,
        previous_state=prev_state,
        resulting_state={"connection_state": new_state.value},
        safe_details={
            "summary": summary,
            "backend_outcome": backend_outcome.model_dump(),
            "agent_outcome": agent_outcome.model_dump(),
        },
    )

    # In-flight protection:
    # A delayed connection result must NOT overwrite a subsequent:
    # - Configuration update (configuration_version changed)
    # - Disconnect (explicitly disconnected while probe was in flight)
    # - Archive (archived while probe was in flight)
    can_update_state = (
        current_project.configuration_version == checked_version
        and current_project.lifecycle != ProjectLifecycle.ARCHIVED.value
        and current_project.connection_state != ProjectConnectionState.DISCONNECTED.value
    )

    if can_update_state:
        current_project.connection_state = new_state.value
        current_project.last_check_timestamp = checked_at
        if new_state in (ProjectConnectionState.CONNECTED, ProjectConnectionState.PARTIAL):
            current_project.last_successful_check_timestamp = checked_at
        current_project.updated_at_utc = checked_at
        db.commit()
        db.refresh(current_project)
    else:
        # A subsequent update, disconnect, or archive occurred while check was in flight.
        # Preserve historical check result in audit trail without incorrectly replacing current state.
        db.commit()

    return ConnectionCheckResponse(
        project_id=project_id,
        configuration_version=checked_version,
        checked_at_utc=checked_at,
        connection_state=new_state.value,
        backend_outcome=backend_outcome,
        agent_outcome=agent_outcome,
        summary=summary,
    )


def disconnect_project(db: Session, user: User, project_id: str) -> Project:
    """Explicitly disconnect a project without touching the external application."""
    project = get_project(db, user, project_id)

    prev_state = {
        "lifecycle": project.lifecycle,
        "connection_state": project.connection_state,
        "configuration_version": project.configuration_version,
    }

    project.connection_state = ProjectConnectionState.DISCONNECTED.value
    project.configuration_version += 1
    project.updated_at_utc = datetime.now(UTC)

    _record_event(
        db=db,
        project_id=project_id,
        user=user,
        event_type=ProjectHistoryEventType.DISCONNECTED,
        config_version=project.configuration_version,
        previous_state=prev_state,
        resulting_state={
            "lifecycle": project.lifecycle,
            "connection_state": project.connection_state,
            "configuration_version": project.configuration_version,
        },
        safe_details={"reason": "User requested disconnect"},
    )

    db.commit()
    db.refresh(project)
    return project


def archive_project(db: Session, user: User, project_id: str) -> Project:
    """Archive a project record, preserving its configuration and history."""
    project = get_project(db, user, project_id)

    if project.lifecycle == ProjectLifecycle.ARCHIVED.value:
        return project

    prev_state = {
        "lifecycle": project.lifecycle,
        "connection_state": project.connection_state,
        "configuration_version": project.configuration_version,
    }

    project.lifecycle = ProjectLifecycle.ARCHIVED.value
    project.configuration_version += 1
    project.updated_at_utc = datetime.now(UTC)

    _record_event(
        db=db,
        project_id=project_id,
        user=user,
        event_type=ProjectHistoryEventType.ARCHIVED,
        config_version=project.configuration_version,
        previous_state=prev_state,
        resulting_state={
            "lifecycle": project.lifecycle,
            "connection_state": project.connection_state,
            "configuration_version": project.configuration_version,
        },
    )

    db.commit()
    db.refresh(project)
    return project


def restore_project(db: Session, user: User, project_id: str) -> Project:
    """Restore an archived project to active status."""
    project = get_project(db, user, project_id)

    if project.lifecycle == ProjectLifecycle.ACTIVE.value:
        return project

    prev_state = {
        "lifecycle": project.lifecycle,
        "connection_state": project.connection_state,
        "configuration_version": project.configuration_version,
    }

    project.lifecycle = ProjectLifecycle.ACTIVE.value
    project.connection_state = ProjectConnectionState.NOT_CHECKED.value
    project.configuration_version += 1
    project.updated_at_utc = datetime.now(UTC)

    _record_event(
        db=db,
        project_id=project_id,
        user=user,
        event_type=ProjectHistoryEventType.RESTORED,
        config_version=project.configuration_version,
        previous_state=prev_state,
        resulting_state={
            "lifecycle": project.lifecycle,
            "connection_state": project.connection_state,
            "configuration_version": project.configuration_version,
        },
    )

    db.commit()
    db.refresh(project)
    return project


def list_project_history(
    db: Session,
    user: User,
    project_id: str,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ProjectHistoryEvent], int]:
    """Retrieve append-only history event audit trail for a project."""
    # Ensure permission
    get_project(db, user, project_id)

    query = select(ProjectHistoryEvent).where(ProjectHistoryEvent.project_id == project_id)
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    offset = max(0, (page - 1) * page_size)
    query = query.order_by(desc(ProjectHistoryEvent.timestamp_utc)).offset(offset).limit(page_size)

    items = db.scalars(query).all()
    return list(items), total


def list_input_references(
    db: Session,
    user: User,
    project_id: str,
) -> list[ProjectInputReference]:
    """List registered input references for a project."""
    get_project(db, user, project_id)
    query = (
        select(ProjectInputReference)
        .where(ProjectInputReference.project_id == project_id)
        .order_by(desc(ProjectInputReference.registered_at_utc))
    )
    return list(db.scalars(query).all())


def add_input_reference(
    db: Session,
    user: User,
    project_id: str,
    data: InputReferenceCreateRequest,
) -> ProjectInputReference:
    """Register a new versioned input reference, preserving existing versions."""
    project = get_project(db, user, project_id)

    ref = ProjectInputReference(
        reference_id=generate_id("ref"),
        project_id=project_id,
        category=data.category.strip(),
        label=data.label.strip(),
        reference_location=data.reference_location.strip(),
        version=data.version.strip() if data.version else "1.0.0",
        registered_at_utc=datetime.now(UTC),
    )
    db.add(ref)

    _record_event(
        db=db,
        project_id=project_id,
        user=user,
        event_type=ProjectHistoryEventType.INPUT_REFERENCE_ADDED,
        config_version=project.configuration_version,
        safe_details={
            "category": ref.category,
            "label": ref.label,
            "version": ref.version,
            "reference_id": ref.reference_id,
        },
    )

    db.commit()
    db.refresh(ref)
    return ref
