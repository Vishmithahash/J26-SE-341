from collections.abc import Callable
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    status,
)
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.api.dependencies import (
    verify_project_access,
)
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
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
from app.components.c1_tool_call_correctness.contracts.correction import (
    CorrectionAttemptRequest,
    CorrectionDiffResponse,
    CorrectionRecord,
    CorrectionSummary,
    ReviewRequest,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
    DiagnosisRequest,
    DiagnosisSummary,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
    ExecutionRequest,
    RunDetailResponse,
    RunSummary,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    ExpectedToolCallSpec,
    GeneratedCandidateCase,
    GenerationJobResponse,
    GenerationRequest,
    GenerationSummary,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import (
    SuiteVersion,
)
from app.components.c1_tool_call_correctness.contracts.reporting import (
    ExportFormat,
    WorkflowReportFilter,
    WorkflowRunReport,
)
from app.components.c1_tool_call_correctness.contracts.research import (
    AccuracyMetricsReport,
    BaselineEvaluationRequest,
    BaselineEvaluationResult,
    BaselineType,
    DatasetSplit,
    ReferenceLabelImportRequest,
    ReferenceLabelImportResponse,
    ReferenceLabelRecord,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationSummary,
)
from app.components.c1_tool_call_correctness.examples.nexacart_live import (
    build_nexacart_live_config,
    is_nexacart_connection,
)
from app.components.c1_tool_call_correctness.examples.nexacart_refund import (
    NEXACART_FIXTURE_DATA,
    NEXACART_USER_REQUEST,
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1CaseExecutionModel,
    C1CorrectionModel,
    C1ExecutionRunModel,
    C1GenerationRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.agent_adapter import (
    AgentExecutionAdapter,
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
from app.components.c1_tool_call_correctness.services import (
    nexacart_correction_service,
    nexacart_defect_lab,
)
from app.components.c1_tool_call_correctness.services.correction_service import (
    CorrectionService,
)
from app.components.c1_tool_call_correctness.services.diagnosis_service import (
    DiagnosisService,
)
from app.components.c1_tool_call_correctness.services.evaluator_baselines import (
    ablated_diagnosis_engine,
    model_baseline_evaluator,
    schema_baseline_evaluator,
)
from app.components.c1_tool_call_correctness.services.execution_service import (
    ExecutionService,
    nexacart_adapter_for_connection,
)
from app.components.c1_tool_call_correctness.services.generation_service import (
    execute_generation_job,
    get_generation_run,
    list_generation_runs,
)
from app.components.c1_tool_call_correctness.services.metrics_engine import (
    metrics_engine,
)
from app.components.c1_tool_call_correctness.services.reporting_service import (
    reporting_service,
)
from app.components.c1_tool_call_correctness.services.research_service import (
    research_service,
)
from app.components.c1_tool_call_correctness.services.suite_selector import (
    extract_agent_facing_task,
)
from app.components.c1_tool_call_correctness.services.validator import (
    validate_project_config,
)
from app.database import SessionLocal, get_db


def get_c1_live_adapter_factory() -> Callable[..., AgentExecutionAdapter]:
    """Factory ``(base_url | None) -> adapter`` for live NexaCart (overridden in hermetic tests).

    ``None`` is the configured NexaCart instance; a base URL is a local defect-lab instance.
    """
    from app.components.c1_tool_call_correctness.services.nexacart_live_adapter import (
        NexaCartLiveAgentAdapter,
    )

    def factory(base_url: str | None = None) -> AgentExecutionAdapter:
        if base_url is None:
            return NexaCartLiveAgentAdapter()
        return NexaCartLiveAgentAdapter.for_base_url(base_url)

    return factory


def get_c1_features() -> dict[str, bool]:
    """Build features of the C1 workspace (overridden in hermetic tests)."""
    from app.config import get_settings

    return {"code_correction_enabled": get_settings().c1_code_correction_enabled}


def _require_code_correction(features: dict[str, bool]) -> None:
    if not features.get("code_correction_enabled"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Code correction and sandbox verification (defect lab) are disabled in this "
                "build (C1_CODE_CORRECTION_ENABLED=false)."
            ),
        )


def get_c1_session_factory() -> Callable[[], Session]:
    """Session factory for background live runs (overridden in hermetic tests)."""
    return SessionLocal


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/c1",
    tags=["Component 1: Tool-Call Correctness"],
    dependencies=[Depends(verify_project_access)],
)

execution_service = ExecutionService()
diagnosis_service = DiagnosisService()
correction_service = CorrectionService()


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
    background_tasks: BackgroundTasks,
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
    session_factory: Annotated[Callable[[], Session], Depends(get_c1_session_factory)],
):
    """Live NexaCart runs return RUNNING at once and continue in the background (poll the run)."""
    try:
        run_model, adapter, is_ready = execution_service.prepare_run(
            db=db,
            project_id=project_id,
            request=payload,
            live_adapter_factory=live_adapter_factory,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if is_ready and run_model.status == "RUNNING":
        if execution_service.is_live_adapter(adapter):
            background_tasks.add_task(
                execution_service.run_prepared_in_background,
                session_factory,
                run_model.id,
                adapter,
            )
        else:
            execution_service.execute_prepared_run(db, run_model.id, adapter)

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
    background_tasks: BackgroundTasks,
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
    session_factory: Annotated[Callable[[], Session], Depends(get_c1_session_factory)],
):
    try:
        run_model, adapter, is_ready = execution_service.prepare_rerun(
            db, project_id, run_id, live_adapter_factory=live_adapter_factory
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    if is_ready:
        attempt = execution_service.next_attempt_number(db, run_model.id)
        if execution_service.is_live_adapter(adapter):
            background_tasks.add_task(
                execution_service.run_prepared_in_background,
                session_factory,
                run_model.id,
                adapter,
                attempt,
            )
        else:
            execution_service.execute_prepared_run(db, run_model.id, adapter, attempt)
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
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
):
    configs = list_project_configs(db, project_id)
    if not configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configurations found for project '{project_id}'.",
        )
    latest_config = configs[0]
    conn_ref = latest_config.agent_connection_ref
    if is_nexacart_connection(conn_ref):
        live_adapter: AgentExecutionAdapter = nexacart_adapter_for_connection(
            conn_ref, live_adapter_factory
        )
    else:
        live_adapter = LiveAgentAdapter(connection_ref=conn_ref)
    is_ready, reason = live_adapter.check_readiness()

    response = {
        "project_id": project_id,
        "config_version": latest_config.version,
        "agent_connection_ref": conn_ref,
        "adapter_type": getattr(live_adapter, "ADAPTER_TYPE", "UNKNOWN"),
        "is_ready": is_ready,
        "diagnostics": reason or "Adapter connection verified and ready.",
    }
    if is_ready and hasattr(live_adapter, "describe"):
        response["execution_target"] = live_adapter.describe()
    return response


# C1 live NexaCart: configuration import and readiness
# ============================================================================


@router.get(
    "/live/nexacart/readiness",
    summary="Check that NexaCart, its QA harness and the agent are reachable for live C1 runs",
)
def nexacart_live_readiness(
    project_id: str,
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
):
    adapter = live_adapter_factory()
    is_ready, reason = adapter.check_readiness()
    caps = getattr(adapter, "capabilities", None) or {}
    return {
        "project_id": project_id,
        "status": "READY" if is_ready else "BLOCKED",
        "reasons": [] if is_ready else [reason or "Live NexaCart target is not ready."],
        "base_url": getattr(getattr(adapter, "target", None), "base_url", None),
        "harness_version": caps.get("harnessVersion"),
        "agent": caps.get("agent") or {},
        "tools": [
            {"name": t.get("name"), "is_state_changing": bool(t.get("isStateChanging"))}
            for t in caps.get("tools", [])
        ],
    }


@router.get("/features", summary="C1 build features shown in the workspace")
def c1_features(
    project_id: str,
    features: Annotated[dict[str, bool], Depends(get_c1_features)],
):
    return {"project_id": project_id, **features}


class DefectLabRequest(BaseModel):
    defect_id: str = Field(..., min_length=1)


@router.get(
    "/live/nexacart/defect-lab",
    summary="Controlled-defect lab status and the available controlled defects",
)
def defect_lab_status(
    project_id: str,
    features: Annotated[dict[str, bool], Depends(get_c1_features)],
):
    if not features.get("code_correction_enabled"):
        return {"enabled": False, "lab": None, "defects": []}
    lab = nexacart_defect_lab.get_lab(project_id)
    return {
        "enabled": True,
        "lab": lab.public() if lab else None,
        "defects": nexacart_defect_lab.available_defects(),
    }


@router.post(
    "/live/nexacart/defect-lab",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Build a disposable NexaCart copy with one controlled defect and run it locally",
)
def start_defect_lab(
    project_id: str,
    payload: DefectLabRequest,
    background_tasks: BackgroundTasks,
    features: Annotated[dict[str, bool], Depends(get_c1_features)],
):
    _require_code_correction(features)
    from pathlib import Path

    from app.config import get_settings

    root = get_settings().nexacart_source_root
    if not root or not Path(root).is_dir():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXACART_SOURCE_ROOT is not configured; the lab copies that tree.",
        )
    try:
        lab = nexacart_defect_lab.begin_lab(project_id, payload.defect_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    background_tasks.add_task(nexacart_defect_lab.build_lab, lab, Path(root))
    return {
        "lab": lab.public(),
        "note": "Building the seeded copy takes about 1-2 minutes.",
    }


@router.delete(
    "/live/nexacart/defect-lab",
    summary="Stop the defect lab instance and delete its disposable copy",
)
def stop_defect_lab(
    project_id: str,
    features: Annotated[dict[str, bool], Depends(get_c1_features)],
):
    _require_code_correction(features)
    lab = nexacart_defect_lab.stop_lab(project_id)
    return {"lab": lab.public() if lab else None}


@router.post(
    "/live/nexacart/config",
    response_model=ProjectConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a C1 configuration version from NexaCart's real tool registry and C1 requirements",
)
def import_nexacart_live_config(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
    features: Annotated[dict[str, bool], Depends(get_c1_features)],
    target: str = "main",
):
    """target=main: the configured NexaCart; target=lab: this project's running defect lab."""
    extra_details: dict[str, Any] = {"target": target}
    if target == "lab":
        _require_code_correction(features)
        lab = nexacart_defect_lab.get_lab(project_id)
        if lab is None or lab.status != "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No running defect lab for this project. Start one first.",
            )
        adapter = live_adapter_factory(lab.base_url)
        extra_details.update(
            {
                "source_root": lab.workspace,
                "controlled_defect": lab.public()["defect"],
                "evidence_kind": "CONTROLLED_DEFECT",
            }
        )
    elif target == "main":
        adapter = live_adapter_factory()
        extra_details["evidence_kind"] = "NATURAL_AGENT_BEHAVIOUR"
    else:
        raise HTTPException(status_code=422, detail="target must be 'main' or 'lab'.")
    is_ready, reason = adapter.check_readiness()
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Live NexaCart target is BLOCKED: {reason}",
        )
    configs = list_project_configs(db, project_id)
    next_version = (configs[0].version + 1) if configs else 1
    payload = build_nexacart_live_config(
        adapter.capabilities or {},
        getattr(adapter.target, "base_url", None) or "",
        version=next_version,
        extra_details=extra_details,
    )
    try:
        model = create_project_config(db, project_id, payload)
    except (ConfigConflictError, ConfigValidationError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _serialize_config_model(model)


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
    current_user: Annotated[User, Depends(require_active_user)],
):
    try:
        return await diagnosis_service.execute_diagnosis(
            db=db,
            project_id=project_id,
            run_id=run_id,
            request=request,
            user_id=current_user.id if current_user else None,
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


@router.post(
    "/corrections/attempts",
    response_model=CorrectionRecord,
    status_code=status.HTTP_200_OK,
    summary="Request automated candidate patch generation and sandbox verification for an eligible defect",
)
async def request_correction_endpoint(
    project_id: str,
    request: CorrectionAttemptRequest,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    live_adapter_factory: Annotated[
        Callable[..., AgentExecutionAdapter], Depends(get_c1_live_adapter_factory)
    ],
    session_factory: Annotated[Callable[[], Session], Depends(get_c1_session_factory)],
):
    """NexaCart attempts return VERIFYING; poll GET /corrections/{id} for each verification step."""

    def schedule(correction_id: str) -> None:
        background_tasks.add_task(
            nexacart_correction_service.verify_attempt,
            session_factory,
            correction_id,
            live_adapter_factory,
        )

    try:
        return await correction_service.execute_correction_attempt(
            db=db,
            project_id=project_id,
            request=request,
            schedule=schedule,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/corrections/{correction_id}",
    response_model=CorrectionRecord,
    summary="Retrieve candidate correction status, verification results, and review decision",
)
def get_correction_endpoint(
    project_id: str,
    correction_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    record = correction_service.get_correction_by_id(db, project_id, correction_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correction '{correction_id}' not found.",
        )
    return record


@router.get(
    "/corrections/{correction_id}/diff",
    response_model=CorrectionDiffResponse,
    summary="Retrieve candidate patch unified diff representation for developer review",
)
def get_correction_diff_endpoint(
    project_id: str,
    correction_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return correction_service.get_correction_diff(db, project_id, correction_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/corrections/{correction_id}/review",
    response_model=CorrectionRecord,
    summary="Submit developer review decision (ACCEPTED or REJECTED) bound to exact candidate patch hash",
)
def review_correction_endpoint(
    project_id: str,
    correction_id: str,
    request: ReviewRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return correction_service.submit_review(
            db=db,
            project_id=project_id,
            correction_id=correction_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/corrections",
    response_model=list[CorrectionSummary],
    summary="Inspect candidate correction attempts history for a project or run",
)
def list_corrections_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    run_id: str | None = None,
    limit: int = 50,
):
    return correction_service.list_corrections(
        db, project_id=project_id, run_id=run_id, limit=limit
    )


# --------------------------------------------------------------------------
# REPORTING & EXPORT ENDPOINTS
# --------------------------------------------------------------------------


@router.get(
    "/reports/workflow",
    response_model=WorkflowRunReport,
    summary="Paginated end-to-end workflow report across execution, diagnosis, correction, and review",
)
def get_workflow_report_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    run_id: str | None = None,
    suite_id: str | None = None,
    verdict: CorrectnessVerdict | None = None,
    cause_category: CauseCategory | None = None,
    is_verified: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    filt = WorkflowReportFilter(
        project_id=project_id,
        run_id=run_id,
        suite_id=suite_id,
        verdict=verdict,
        cause_category=cause_category,
        is_verified=is_verified,
        limit=limit,
        offset=offset,
    )
    return reporting_service.generate_workflow_report(db, filt)


@router.get(
    "/reports/export",
    summary="Export machine-readable workflow report as redacted JSON or tabular CSV",
)
def export_workflow_report_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    run_id: str | None = None,
    format: ExportFormat = ExportFormat.JSON,
):
    filt = WorkflowReportFilter(
        project_id=project_id,
        run_id=run_id,
        limit=500,
        offset=0,
    )
    report = reporting_service.generate_workflow_report(db, filt)

    if format == ExportFormat.CSV:
        csv_content = reporting_service.export_report_csv(report)
        return Response(content=csv_content, media_type="text/csv")

    json_content = reporting_service.export_report_json(report)
    return Response(content=json_content, media_type="application/json")


# --------------------------------------------------------------------------
# RESEARCH DATA & INDEPENDENT LABELS
# --------------------------------------------------------------------------


@router.post(
    "/research/labels",
    response_model=ReferenceLabelImportResponse,
    summary="Import independently reviewed ground truth reference labels with task_family split isolation",
)
def import_reference_labels_endpoint(
    project_id: str,
    request: ReferenceLabelImportRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return research_service.import_reference_labels(
            db=db, project_id=project_id, request=request
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/research/labels",
    response_model=list[ReferenceLabelRecord],
    summary="Inspect independently reviewed ground truth reference labels",
)
def list_reference_labels_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    dataset_split: DatasetSplit | None = None,
    task_family: str | None = None,
    label_version: str | None = None,
):
    return research_service.list_reference_labels(
        db=db,
        project_id=project_id,
        dataset_split=dataset_split,
        task_family=task_family,
        label_version=label_version,
    )


# --------------------------------------------------------------------------
# RESEARCH METRICS & BASELINES
# --------------------------------------------------------------------------


@router.post(
    "/research/metrics",
    response_model=AccuracyMetricsReport,
    summary="Compute documented accuracy, diagnosis, code localisation, and verification metrics",
)
def compute_research_metrics_endpoint(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    run_id: str | None = None,
    dataset_split: DatasetSplit | None = None,
):
    # 1. Fetch labels
    labels = research_service.list_reference_labels(
        db, project_id=project_id, dataset_split=dataset_split
    )
    if not labels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No reference labels found for project '{project_id}' in split '{dataset_split}'.",
        )

    # 2. Fetch executions
    case_query = (
        select(C1CaseExecutionModel)
        .join(
            C1ExecutionRunModel,
            C1CaseExecutionModel.run_id == C1ExecutionRunModel.id,
        )
        .where(C1ExecutionRunModel.project_id == project_id)
    )
    if run_id:
        case_query = case_query.where(C1CaseExecutionModel.run_id == run_id)

    raw_cases = db.scalars(case_query).all()
    executions: list[CaseExecutionDetail] = []
    for rc in raw_cases:
        executions.append(
            CaseExecutionDetail(
                execution_id=rc.id,
                case_id=rc.case_id,
                attempt_number=rc.attempt_number,
                session_id=rc.session_id,
                readiness_status=rc.readiness_status,
                execution_status=rc.execution_status,
                verdict=rc.verdict,
                trace_completeness=rc.trace_completeness,
                error_message=rc.error_message,
                resolved_expectations=rc.resolved_expectations or [],
                captured_events=rc.captured_events or [],
                check_results=rc.check_results or [],
            )
        )

    # 3. Fetch diagnoses
    diag_query = select(C1CaseDiagnosisModel).where(
        C1CaseDiagnosisModel.project_id == project_id
    )
    if run_id:
        diag_query = diag_query.where(C1CaseDiagnosisModel.run_id == run_id)

    raw_diags = db.scalars(diag_query).all()
    diagnoses: list[CaseDiagnosisRecord] = []
    for rd in raw_diags:
        locs = []
        for l in rd.candidate_code_locations or []:
            try:
                locs.append(CandidateCodeLocation.model_validate(l))
            except (ValidationError, ValueError, TypeError, KeyError):
                pass

        diagnoses.append(
            CaseDiagnosisRecord(
                diagnosis_id=rd.id,
                run_id=rd.run_id,
                case_id=rd.case_id,
                attempt_number=rd.attempt_number,
                cause_category=CauseCategory(rd.cause_category),
                explanation_summary=rd.explanation_summary,
                check_explanations=[],
                candidate_code_locations=locs,
                evidence_refs=rd.evidence_refs or [],
                source_hash=rd.source_hash,
                explanation_method=rd.explanation_method,
                metrics=rd.metrics or {},
            )
        )

    # 4. Fetch corrections
    corr_query = select(C1CorrectionModel).where(
        C1CorrectionModel.project_id == project_id
    )
    if run_id:
        corr_query = corr_query.where(C1CorrectionModel.run_id == run_id)
    raw_corrs = db.scalars(corr_query).all()
    corrections = [
        {
            "correction_id": rc.id,
            "case_id": rc.case_id,
            "status": rc.status,
            "is_verified": rc.is_verified,
            "verification_results": rc.verification_results or [],
            "metrics": rc.metrics or {},
        }
        for rc in raw_corrs
    ]

    return metrics_engine.compute_metrics(
        project_id=project_id,
        run_id=run_id,
        dataset_split=dataset_split,
        reference_labels=labels,
        executions=executions,
        diagnoses=diagnoses,
        corrections=corrections,
    )


@router.post(
    "/research/baselines/evaluate",
    response_model=BaselineEvaluationResult,
    summary="Run comparative baseline or ablated diagnosis on an existing captured execution",
)
def evaluate_baseline_endpoint(
    project_id: str,
    request: BaselineEvaluationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    # Fetch case execution
    stmt = (
        select(C1CaseExecutionModel)
        .join(
            C1ExecutionRunModel,
            C1CaseExecutionModel.run_id == C1ExecutionRunModel.id,
        )
        .where(
            C1ExecutionRunModel.project_id == project_id,
            C1CaseExecutionModel.run_id == request.run_id,
            C1CaseExecutionModel.case_id == request.case_id,
        )
    )
    case_model = db.scalar(stmt)
    if not case_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case execution '{request.case_id}' in run '{request.run_id}' not found.",
        )

    raw_events = case_model.captured_events or []
    captured_events = []
    for ev in raw_events:
        try:
            captured_events.append(CapturedToolEvent.model_validate(ev))
        except (ValidationError, ValueError, TypeError, KeyError):
            pass

    raw_specs = case_model.resolved_expectations or []
    resolved_expectations = []
    for spec in raw_specs:
        try:
            resolved_expectations.append(ExpectedToolCallSpec.model_validate(spec))
        except (ValidationError, ValueError, TypeError, KeyError):
            pass

    try:
        readiness_status = CaseReadinessStatus(case_model.readiness_status)
    except (ValueError, TypeError, KeyError):
        readiness_status = CaseReadinessStatus.CONFIGURED

    try:
        execution_status = CaseExecutionStatus(case_model.execution_status)
    except (ValueError, TypeError, KeyError):
        execution_status = CaseExecutionStatus.EXECUTED

    try:
        verdict = CorrectnessVerdict(case_model.verdict)
    except (ValueError, TypeError, KeyError):
        verdict = CorrectnessVerdict.FAIL

    try:
        trace_completeness = TraceCompleteness(case_model.trace_completeness)
    except (ValueError, TypeError, KeyError):
        trace_completeness = TraceCompleteness.COMPLETE

    exec_detail = CaseExecutionDetail(
        execution_id=case_model.id,
        case_id=case_model.case_id,
        attempt_number=case_model.attempt_number,
        session_id=case_model.session_id,
        readiness_status=readiness_status,
        execution_status=execution_status,
        verdict=verdict,
        trace_completeness=trace_completeness,
        error_message=case_model.error_message,
        resolved_expectations=resolved_expectations,
        captured_events=captured_events,
        check_results=[],
    )

    if request.baseline_type == BaselineType.SCHEMA_AND_CALL_ONLY:
        # Load tool definitions from latest project config
        cfgs = list_project_configs(db, project_id)
        cfg = cfgs[0] if cfgs else None
        tool_defs = {}
        if cfg and cfg.tools:
            for t in cfg.tools:
                try:
                    tool_defs[t["name"]] = ToolDefinition.model_validate(t)
                except (ValidationError, ValueError, TypeError, KeyError):
                    pass
        return schema_baseline_evaluator.evaluate_case(exec_detail, tool_defs)

    elif request.baseline_type == BaselineType.MODEL_ARGUMENT_JUDGE:
        return model_baseline_evaluator.evaluate_case(exec_detail)

    else:
        # Ablated diagnosis
        return ablated_diagnosis_engine.run_ablated_diagnosis(
            exec_detail, request.baseline_type
        )
