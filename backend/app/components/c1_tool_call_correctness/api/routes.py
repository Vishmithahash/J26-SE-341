from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
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
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    DiagnosisRequest,
    DiagnosisSummary,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
    ExecutionRequest,
    RunDetailResponse,
    RunSummary,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    GeneratedCandidateCase,
    GenerationJobResponse,
    GenerationRequest,
    GenerationSummary,
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
    C1GenerationRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.agent_adapter import (
    LiveAgentAdapter,
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
from app.components.c1_tool_call_correctness.services.diagnosis_service import (
    DiagnosisService,
)
from app.components.c1_tool_call_correctness.services.execution_service import (
    ExecutionService,
)
from app.components.c1_tool_call_correctness.services.generation_service import (
    execute_generation_job,
    get_generation_run,
    list_generation_runs,
)
from app.components.c1_tool_call_correctness.services.suite_selector import (
    extract_agent_facing_task,
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

execution_service = ExecutionService()
diagnosis_service = DiagnosisService()


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


def _serialize_generation_run(model: C1GenerationRunModel) -> GenerationJobResponse:
    req_dict = model.request_payload or {}
    return GenerationJobResponse(
        job_id=model.id,
        project_id=model.project_id,
        config_id=model.config_id,
        config_version=req_dict.get("config_version", 1),
        status=model.status,
        content_hash=model.content_hash,
        summary=GenerationSummary(**model.summary),
        suite_version_id=model.suite_version_id,
        created_at=model.created_at,
    )


@router.post(
    "/generation/jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger automatic candidate generation and validation",
)
def create_generation_job_endpoint(
    project_id: str,
    payload: GenerationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        run_record, _, _, _ = execute_generation_job(db, project_id, payload)
        return _serialize_generation_run(run_record)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.get(
    "/generation/jobs",
    response_model=list[GenerationJobResponse],
    summary="List generation runs for project",
)
def list_generation_jobs_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    runs = list_generation_runs(db, project_id)
    return [_serialize_generation_run(r) for r in runs]


@router.get(
    "/generation/jobs/{job_id}",
    response_model=GenerationJobResponse,
    summary="Get generation run status and metrics",
)
def get_generation_job_endpoint(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    run = get_generation_run(db, project_id, job_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found for project '{project_id}'.",
        )
    return _serialize_generation_run(run)


@router.get(
    "/generation/jobs/{job_id}/candidates",
    response_model=list[GeneratedCandidateCase],
    summary="Inspect generated candidate cases and validation issues",
)
def get_job_candidates_endpoint(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    valid_only: bool = False,
):
    run = get_generation_run(db, project_id, job_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found for project '{project_id}'.",
        )
    cases = [GeneratedCandidateCase(**c) for c in (run.candidates or [])]
    if valid_only:
        cases = [c for c in cases if c.is_valid]
    return cases


@router.get(
    "/generation/jobs/{job_id}/agent-tasks",
    response_model=list[AgentFacingTask],
    summary="Retrieve agent-facing task payloads isolated from QA expectations",
)
def get_job_agent_tasks_endpoint(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    run = get_generation_run(db, project_id, job_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found for project '{project_id}'.",
        )
    cases = [
        GeneratedCandidateCase(**c)
        for c in (run.candidates or [])
        if c.get("is_valid", True) and not c.get("rejection_reason")
    ]
    return [extract_agent_facing_task(c) for c in cases]


class PromoteSuitePayload(BaseModel):
    suite_id: str
    name: str


@router.post(
    "/generation/jobs/{job_id}/promote-suite",
    response_model=SuiteVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Promote selected valid candidates of a generation run into an accepted immutable suite",
)
def promote_suite_from_job_endpoint(
    project_id: str,
    job_id: str,
    payload: PromoteSuitePayload,
    db: Annotated[Session, Depends(get_db)],
):
    run = get_generation_run(db, project_id, job_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found for project '{project_id}'.",
        )
    selected_cases = [
        c
        for c in (run.candidates or [])
        if c.get("is_valid", True) and not c.get("rejection_reason")
    ]
    if not selected_cases:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot promote suite: no valid accepted candidates found in generation run.",
        )

    suite_ver = create_suite_version(
        db=db,
        project_id=project_id,
        suite_id=payload.suite_id,
        name=payload.name,
        config_id=run.config_id,
        cases=selected_cases,
    )
    suite_ver.content_hash = run.content_hash
    suite_ver.generation_run_id = run.id
    run.suite_id = payload.suite_id
    run.suite_version_id = suite_ver.id
    db.commit()
    db.refresh(suite_ver)

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


@router.get(
    "/suites",
    response_model=list[SuiteVersion],
    summary="List accepted test suite versions for project",
)
def list_suites_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    stmt = (
        select(C1SuiteVersionModel)
        .where(C1SuiteVersionModel.project_id == project_id)
        .order_by(C1SuiteVersionModel.created_at.desc())
    )
    suites = list(db.execute(stmt).scalars().all())
    return [
        SuiteVersion(
            suite_id=s.suite_id,
            project_id=s.project_id,
            version=s.version,
            name=s.name,
            config_id=s.config_id,
            case_versions=[],
            is_immutable=s.is_immutable,
            created_at=s.created_at,
        )
        for s in suites
    ]


@router.get(
    "/suites/{suite_id}",
    response_model=SuiteVersion,
    summary="Retrieve accepted suite version",
)
def get_suite_endpoint(
    project_id: str,
    suite_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    stmt = (
        select(C1SuiteVersionModel)
        .where(
            C1SuiteVersionModel.project_id == project_id,
            C1SuiteVersionModel.suite_id == suite_id,
        )
        .order_by(C1SuiteVersionModel.version.desc())
    )
    suite = db.execute(stmt).scalars().first()
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite '{suite_id}' not found for project '{project_id}'.",
        )
    return SuiteVersion(
        suite_id=suite.suite_id,
        project_id=suite.project_id,
        version=suite.version,
        name=suite.name,
        config_id=suite.config_id,
        case_versions=[],
        is_immutable=suite.is_immutable,
        created_at=suite.created_at,
    )


@router.get(
    "/suites/{suite_id}/cases/{case_id}/agent-view",
    response_model=AgentFacingTask,
    summary="Retrieve isolated agent-facing task view for a case in an accepted suite",
)
def get_suite_case_agent_view_endpoint(
    project_id: str,
    suite_id: str,
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    stmt = (
        select(C1SuiteVersionModel)
        .where(
            C1SuiteVersionModel.project_id == project_id,
            C1SuiteVersionModel.suite_id == suite_id,
        )
        .order_by(C1SuiteVersionModel.version.desc())
    )
    suite = db.execute(stmt).scalars().first()
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite '{suite_id}' not found for project '{project_id}'.",
        )
    for c_data in suite.cases or []:
        if c_data.get("case_id") == case_id:
            candidate = GeneratedCandidateCase(**c_data)
            return extract_agent_facing_task(candidate)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Case '{case_id}' not found in suite '{suite_id}'.",
    )


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


# ============================================================================
# C1-03: Execution, Evidence Capture, and Correctness Evaluation Routes
# ============================================================================


@router.post(
    "/runs",
    response_model=RunDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a test execution run on an accepted, frozen suite version",
)
def start_execution_run_endpoint(
    project_id: str,
    payload: ExecutionRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        run_model = execution_service.create_and_start_run(
            db=db,
            project_id=project_id,
            request=payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    detail = execution_service.get_run_detail(db, project_id, run_model.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution run record after start.",
        )
    return detail


@router.get(
    "/runs",
    response_model=list[RunSummary],
    summary="List execution runs for a project with optional verdict filtering",
)
def list_execution_runs_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    verdict: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return execution_service.list_runs(
        db=db,
        project_id=project_id,
        verdict=verdict,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Retrieve full execution run details and case evaluations",
)
def get_execution_run_endpoint(
    project_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    detail = execution_service.get_run_detail(db, project_id, run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution run '{run_id}' not found for project '{project_id}'.",
        )
    return detail


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunDetailResponse,
    summary="Cancel an active execution run",
)
def cancel_execution_run_endpoint(
    project_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        execution_service.cancel_run(db, project_id, run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    detail = execution_service.get_run_detail(db, project_id, run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    return detail


@router.post(
    "/runs/{run_id}/rerun",
    response_model=RunDetailResponse,
    summary="Rerun a test suite run, recording a new execution attempt without overwriting history",
)
def rerun_execution_endpoint(
    project_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        execution_service.rerun_execution(db, project_id, run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    detail = execution_service.get_run_detail(db, project_id, run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve run record after rerun.",
        )
    return detail


@router.get(
    "/runs/{run_id}/cases/{case_id}",
    response_model=CaseExecutionDetail,
    summary="Retrieve check-level evaluation results, evidence refs, and traces for a case execution",
)
def get_case_execution_endpoint(
    project_id: str,
    run_id: str,
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    case_detail = execution_service.get_case_execution_detail(
        db, project_id, run_id, case_id
    )
    if not case_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case execution for case '{case_id}' in run '{run_id}' not found.",
        )
    return case_detail


@router.get(
    "/adapter/readiness",
    summary="Validate connection and readiness of the configured agent adapter",
)
def check_adapter_readiness_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    configs = list_project_configs(db, project_id)
    if not configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configurations found for project '{project_id}'.",
        )
    latest_config = configs[0]
    conn_ref = latest_config.agent_connection_ref
    live_adapter = LiveAgentAdapter(connection_ref=conn_ref)
    is_ready, reason = live_adapter.check_readiness()

    return {
        "project_id": project_id,
        "config_version": latest_config.version,
        "agent_connection_ref": conn_ref,
        "is_ready": is_ready,
        "diagnostics": reason or "Adapter connection verified and ready.",
    }


@router.post(
    "/runs/{run_id}/diagnose",
    response_model=list[CaseDiagnosisRecord],
    status_code=status.HTTP_200_OK,
    summary="Request evidence-linked explanations and supported root cause diagnosis for an execution run",
)
async def diagnose_run_endpoint(
    project_id: str,
    run_id: str,
    request: DiagnosisRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return await diagnosis_service.execute_diagnosis(
            db=db,
            project_id=project_id,
            run_id=run_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/diagnoses/{diagnosis_id}",
    response_model=CaseDiagnosisRecord,
    summary="Retrieve a specific failure explanation and diagnosis record",
)
def get_diagnosis_endpoint(
    project_id: str,
    diagnosis_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    record = diagnosis_service.get_diagnosis_by_id(db, project_id, diagnosis_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnosis '{diagnosis_id}' not found.",
        )
    return record


@router.get(
    "/runs/{run_id}/cases/{case_id}/diagnosis",
    response_model=CaseDiagnosisRecord,
    summary="Retrieve failure explanation and diagnosis for a specific case in a run",
)
def get_case_diagnosis_endpoint(
    project_id: str,
    run_id: str,
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    record = diagnosis_service.get_case_diagnosis(db, project_id, run_id, case_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnosis for case '{case_id}' in run '{run_id}' not found.",
        )
    return record


@router.get(
    "/diagnoses/{diagnosis_id}/code-locations",
    response_model=list[CandidateCodeLocation],
    summary="Retrieve evidence-linked candidate code locations for a diagnosis",
)
def get_diagnosis_code_locations_endpoint(
    project_id: str,
    diagnosis_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return diagnosis_service.get_candidate_code_locations(
            db, project_id, diagnosis_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/diagnoses",
    response_model=list[DiagnosisSummary],
    summary="Inspect diagnosis history for a project or run",
)
def list_diagnoses_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    run_id: str | None = None,
    limit: int = 50,
):
    return diagnosis_service.list_diagnoses(
        db, project_id=project_id, run_id=run_id, limit=limit
    )
