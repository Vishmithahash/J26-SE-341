import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ProjectConfigCreate,
    ProjectConfigUpdate,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationSummary,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.validator import (
    validate_project_config,
)


class ConfigServiceError(Exception):
    """Base exception for configuration service errors."""


class ConfigNotFoundError(ConfigServiceError):
    """Raised when a requested configuration is not found within the project scope."""


class ImmutableConfigError(ConfigServiceError):
    """Raised when an attempt is made to mutate an immutable (accepted/locked) configuration version."""


class ConfigConflictError(ConfigServiceError):
    """Raised when a version conflict occurs for a project."""


class ConfigValidationError(ConfigServiceError):
    """Raised when configuration specification fails semantic validation."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def list_project_configs(db: Session, project_id: str) -> list[C1ProjectConfigModel]:
    """Retrieves all configuration versions scoped strictly to the specified project."""
    stmt = (
        select(C1ProjectConfigModel)
        .where(C1ProjectConfigModel.project_id == project_id)
        .order_by(C1ProjectConfigModel.version.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_project_config(
    db: Session, project_id: str, config_id: str
) -> C1ProjectConfigModel | None:
    """Retrieves a single configuration version.
    Strictly filters by both config_id and project_id to prevent cross-project access.
    """
    stmt = select(C1ProjectConfigModel).where(
        C1ProjectConfigModel.id == config_id,
        C1ProjectConfigModel.project_id == project_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def create_project_config(
    db: Session,
    project_id: str,
    payload: ProjectConfigCreate,
    enforce_validation: bool = True,
) -> C1ProjectConfigModel:
    """Creates and persists a new project configuration version."""
    if enforce_validation:
        summary = validate_project_config(payload)
        if not summary.is_valid:
            first_err = (
                summary.issues[0].message if summary.issues else "Validation failed"
            )
            raise ConfigValidationError(
                f"Configuration validation failed: {first_err}", summary
            )

    # Check for version uniqueness within the project
    stmt = select(C1ProjectConfigModel).where(
        C1ProjectConfigModel.project_id == project_id,
        C1ProjectConfigModel.version == payload.version,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise ConfigConflictError(
            f"Configuration version {payload.version} already exists for project '{project_id}'."
        )

    now = datetime.now(UTC)
    config = C1ProjectConfigModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=payload.version,
        is_immutable=False,
        agent_connection_ref=payload.agent_connection_ref,
        tools=[t.model_dump() for t in payload.tools],
        requirements=[r.model_dump() for r in payload.requirements],
        tool_constraints=payload.tool_constraints.model_dump(),
        expectations=payload.expectations,
        synthetic_fixture_refs=payload.synthetic_fixture_refs,
        reset_capability=payload.reset_capability.model_dump()
        if payload.reset_capability
        else None,
        trace_capabilities=[tc.model_dump() for tc in payload.trace_capabilities],
        created_at=now,
        updated_at=now,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_project_config(
    db: Session,
    project_id: str,
    config_id: str,
    payload: ProjectConfigUpdate,
    enforce_validation: bool = True,
) -> C1ProjectConfigModel:
    """Updates an existing project configuration version.
    Rejects modification if the version is immutable.
    """
    config = get_project_config(db, project_id, config_id)
    if not config:
        raise ConfigNotFoundError(
            f"Configuration '{config_id}' not found for project '{project_id}'."
        )

    if config.is_immutable:
        raise ImmutableConfigError(
            f"Configuration version {config.version} (ID '{config_id}') is immutable "
            "because it is bound to an accepted test suite or executed run."
        )

    if payload.agent_connection_ref is not None:
        config.agent_connection_ref = payload.agent_connection_ref
    if payload.tools is not None:
        config.tools = [t.model_dump() for t in payload.tools]
    if payload.requirements is not None:
        config.requirements = [r.model_dump() for r in payload.requirements]
    if payload.tool_constraints is not None:
        config.tool_constraints = payload.tool_constraints.model_dump()
    if payload.expectations is not None:
        config.expectations = payload.expectations
    if payload.synthetic_fixture_refs is not None:
        config.synthetic_fixture_refs = payload.synthetic_fixture_refs
    if payload.reset_capability is not None:
        config.reset_capability = (
            payload.reset_capability.model_dump() if payload.reset_capability else None
        )
    if payload.trace_capabilities is not None:
        config.trace_capabilities = [
            tc.model_dump() for tc in payload.trace_capabilities
        ]

    config.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(config)
    return config


def create_suite_version(
    db: Session, project_id: str, suite_id: str, name: str, config_id: str, cases: list
) -> C1SuiteVersionModel:
    """Creates an accepted test suite version and immutably freezes the referenced configuration."""
    config = get_project_config(db, project_id, config_id)
    if not config:
        raise ConfigNotFoundError(
            f"Configuration '{config_id}' not found for project '{project_id}'."
        )

    # Lock referenced configuration to guarantee immutability
    config.is_immutable = True
    config.updated_at = datetime.now(UTC)

    # Determine next suite version
    stmt = (
        select(C1SuiteVersionModel)
        .where(
            C1SuiteVersionModel.project_id == project_id,
            C1SuiteVersionModel.suite_id == suite_id,
        )
        .order_by(C1SuiteVersionModel.version.desc())
    )
    latest = db.execute(stmt).scalars().first()
    next_ver = (latest.version + 1) if latest else 1

    suite_version = C1SuiteVersionModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        suite_id=suite_id,
        version=next_ver,
        name=name,
        config_id=config_id,
        is_immutable=True,
        cases=cases,
        created_at=datetime.now(UTC),
    )
    db.add(suite_version)
    db.commit()
    db.refresh(suite_version)
    return suite_version
