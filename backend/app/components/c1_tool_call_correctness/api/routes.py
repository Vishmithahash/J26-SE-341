from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.api.dependencies import (
    verify_project_access,
)
from app.components.c1_tool_call_correctness.contracts.configuration import (
    ProjectConfigCreate,
    ProjectConfigResponse,
    ProjectConfigUpdate,
    ResetCapability,
    TaskRequirement,
    ToolConstraints,
    ToolDefinition,
    TraceCapability,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import (
    SuiteVersion,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationSummary,
)
from app.components.c1_tool_call_correctness.examples.nexacart_refund import (
    NEXACART_FIXTURE_DATA,
    NEXACART_USER_REQUEST,
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)
from app.components.c1_tool_call_correctness.services.config_service import (
    ConfigConflictError,
    ConfigNotFoundError,
    ConfigValidationError,
    ImmutableConfigError,
    create_project_config,
    create_suite_version,
    get_project_config,
    list_project_configs,
    update_project_config,
)
from app.components.c1_tool_call_correctness.services.validator import (
    validate_project_config,
)
from app.database import get_db

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/c1",
    tags=["Component 1: Tool-Call Correctness"],
    dependencies=[Depends(verify_project_access)],
)


def _serialize_config_model(model: C1ProjectConfigModel) -> ProjectConfigResponse:
    return ProjectConfigResponse(
        id=model.id,
        project_id=model.project_id,
        version=model.version,
        is_immutable=model.is_immutable,
        agent_connection_ref=model.agent_connection_ref,
        tools=[ToolDefinition(**t) for t in (model.tools or [])],
        requirements=[TaskRequirement(**r) for r in (model.requirements or [])],
        tool_constraints=ToolConstraints(**(model.tool_constraints or {})),
        expectations=model.expectations or {},
        synthetic_fixture_refs=model.synthetic_fixture_refs or [],
        reset_capability=ResetCapability(**model.reset_capability)
        if model.reset_capability
        else None,
        trace_capabilities=[
            TraceCapability(**tc) for tc in (model.trace_capabilities or [])
        ],
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.post(
    "/configs",
    response_model=ProjectConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project configuration version",
)
def create_config_endpoint(
    project_id: str,
    payload: ProjectConfigCreate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        config = create_project_config(db, project_id, payload)
        return _serialize_config_model(config)
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(exc),
                "validation_summary": exc.summary.model_dump(),
            },
        )
    except ConfigConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/configs",
    response_model=list[ProjectConfigResponse],
    summary="List all configuration versions for the project",
)
def list_configs_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    configs = list_project_configs(db, project_id)
    return [_serialize_config_model(c) for c in configs]


@router.get(
    "/configs/{config_id}",
    response_model=ProjectConfigResponse,
    summary="Retrieve a specific configuration version",
)
def get_config_endpoint(
    project_id: str,
    config_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    config = get_project_config(db, project_id, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration '{config_id}' not found for project '{project_id}'.",
        )
    return _serialize_config_model(config)


@router.put(
    "/configs/{config_id}",
    response_model=ProjectConfigResponse,
    summary="Update a mutable configuration version",
)
def update_config_endpoint(
    project_id: str,
    config_id: str,
    payload: ProjectConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        config = update_project_config(db, project_id, config_id, payload)
        return _serialize_config_model(config)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ImmutableConfigError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(exc),
                "validation_summary": exc.summary.model_dump(),
            },
        )


@router.post(
    "/configs/{config_id}/validate",
    response_model=ValidationSummary,
    summary="Semantically validate a stored configuration",
)
def validate_stored_config_endpoint(
    project_id: str,
    config_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    config = get_project_config(db, project_id, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration '{config_id}' not found for project '{project_id}'.",
        )
    spec = ProjectConfigCreate(
        version=config.version,
        agent_connection_ref=config.agent_connection_ref,
        tools=[ToolDefinition(**t) for t in (config.tools or [])],
        requirements=[TaskRequirement(**r) for r in (config.requirements or [])],
        tool_constraints=ToolConstraints(**(config.tool_constraints or {})),
        expectations=config.expectations or {},
        synthetic_fixture_refs=config.synthetic_fixture_refs or [],
        reset_capability=ResetCapability(**config.reset_capability)
        if config.reset_capability
        else None,
        trace_capabilities=[
            TraceCapability(**tc) for tc in (config.trace_capabilities or [])
        ],
    )
    return validate_project_config(spec)


@router.post(
    "/configs/validate-spec",
    response_model=ValidationSummary,
    summary="Validate an arbitrary configuration specification without saving",
)
def validate_transient_spec_endpoint(project_id: str, payload: ProjectConfigCreate):
    return validate_project_config(payload)


class SuiteCreatePayload(ProjectConfigUpdate):
    suite_id: str
    name: str
    config_id: str
    cases: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/suites",
    response_model=SuiteVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Accept and lock a test suite version, immutably freezing referenced configuration",
)
def create_suite_version_endpoint(
    project_id: str,
    payload: SuiteCreatePayload,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        suite_ver = create_suite_version(
            db=db,
            project_id=project_id,
            suite_id=payload.suite_id,
            name=payload.name,
            config_id=payload.config_id,
            cases=payload.cases,
        )
        return SuiteVersion(
            suite_id=suite_ver.suite_id,
            project_id=suite_ver.project_id,
            version=suite_ver.version,
            name=suite_ver.name,
            config_id=suite_ver.config_id,
            case_versions=[],
            is_immutable=suite_ver.is_immutable,
            created_at=suite_ver.created_at,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/examples/nexacart", summary="Get synthetic NexaCart refund example configuration"
)
def get_nexacart_example_endpoint(project_id: str):
    example_config = get_nexacart_refund_example_config()
    return {
        "user_request": NEXACART_USER_REQUEST,
        "config": example_config.model_dump(),
        "fixture_context": NEXACART_FIXTURE_DATA,
        "note": "Example configuration for testing tool selection and argument relationships.",
    }
