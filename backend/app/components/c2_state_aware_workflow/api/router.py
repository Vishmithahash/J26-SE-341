"""FastAPI router for C2: State-Aware Multi-Step Workflow Testing APIs."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselineType,
)
from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
    InsufficientInputError,
)
from app.components.c2_state_aware_workflow.contracts.coverage import (
    DetailedObservedCoverage,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
    FirstDivergenceDetail,
    ReproductionVerificationResult,
    RuntimeVerdict,
    ViolationDetail,
    WorkflowCoverageSummary,
)
from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
    ExperimentDatasetManifest,
)
from app.components.c2_state_aware_workflow.contracts.report import (
    C2ReportContributionContract,
    C2SuiteReportContract,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    AgentTaskPayload,
    ExecutionMode,
    GeneratedTestDefinition,
    GenerateTestSuiteRequest,
    QASuiteExport,
    TestSuiteDiagnostics,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.evaluator.fixtures import (
    ControlledTraceFixtures,
    ScriptedDemonstrationAgent,
)
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.service import (
    WorkflowEvaluationService,
)
from app.components.c2_state_aware_workflow.evaluator.sut import (
    SyntheticRefundSUT,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.experiments.benchmark import (
    BenchmarkSuiteBuilder,
)
from app.components.c2_state_aware_workflow.experiments.runner import (
    ExperimentRunner,
)
from app.components.c2_state_aware_workflow.generator.readiness import (
    ModelNotReadyError,
)
from app.components.c2_state_aware_workflow.generator.service import (
    TestGenerationService,
)
from app.components.c2_state_aware_workflow.integrations.reporting import (
    C2ReportExportService,
    C2ReportPublisher,
)
from app.components.c2_state_aware_workflow.integrations.service import (
    C2IntegrationService,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2EvaluationResult,
    C2Experiment,
    C2TestCase,
    C2TestSuite,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    ApprovalBlockedError,
    ApprovedModelImmutableError,
    C2ModelRepository,
    ConflictingEvidenceIntegrityError,
    DatasetNotFoundError,
    ModelAlreadyExistsError,
    ModelNotFoundError,
    TestCaseNotFoundError,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project
from app.shared.projects.service import get_project

DbSession = Annotated[Session, Depends(get_db)]


def authorize_c2_project_access(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: DbSession,
) -> Project:
    """Authorize access to project-scoped C2 operations using shared platform policies.

    Enforces:
    1. Authenticated, active account dependency (require_active_user).
    2. Unknown roles are denied with 403 Forbidden.
    3. Project existence and access enforcement:
       - USER may access only projects permitted by the existing ownership policy.
       - ADMIN follows the existing shared administrative access policy.
       - Missing or inaccessible projects follow the existing API error convention (404).
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for account role.",
        )
    return get_project(db, current_user, project_id)


router = APIRouter(
    prefix="/api/v1/c2",
    tags=["c2-state-aware-workflow"],
    dependencies=[Depends(authorize_c2_project_access)],
)


class ApprovalRequest(BaseModel):
    reviewer_id: str = Field(
        ..., description="Identity of the reviewer (labelled self-reported in dev mode)"
    )
    review_basis: str = Field(
        ..., description="Specification or test basis for approval decision"
    )
    review_notes: str | None = Field(
        default=None, description="Detailed review observations and rationale"
    )
    review_type: str = Field(
        default="SELF_REPORTED_DEVELOPMENT",
        description="Review provenance classification",
    )


class NewDraftVersionRequest(BaseModel):
    new_version: str = Field(
        ..., description="New semantic version string, e.g. '1.1.0'"
    )
    description: str | None = None


class C2WorkflowModelSummaryResponse(BaseModel):
    id: str
    project_id: str
    model_id: str
    version: str
    schema_version: str
    name: str
    description: str | None
    content_hash: str
    lifecycle_status: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class C2WorkflowModelResponse(C2WorkflowModelSummaryResponse):
    definition: dict[str, Any]
    review_basis: str | None
    review_notes: str | None


class C2ValidationReportResponse(BaseModel):
    id: str
    model_record_id: str
    project_id: str
    model_id: str
    version: str
    content_hash: str
    is_valid: bool
    readiness: str
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    created_at: datetime


class ModelReadinessResponse(BaseModel):
    project_id: str
    model_id: str
    version: str
    lifecycle_status: str
    readiness: str
    is_approved: bool
    content_hash: str
    validation_passed: bool
    reasons: list[str]


class C2TestSuiteSummaryResponse(BaseModel):
    id: str
    project_id: str
    suite_id: str
    model_id: str
    model_version: str
    model_content_hash: str
    generator_version: str
    seed: int
    total_cases: int
    ready_cases_count: int
    not_ready_cases_count: int
    category_counts: dict[str, int]
    created_at: datetime


class C2TestSuiteResponse(C2TestSuiteSummaryResponse):
    config: dict[str, Any]
    diagnostics: dict[str, Any]


class C2TestCaseSummaryResponse(BaseModel):
    id: str
    project_id: str
    suite_id: str
    test_id: str
    category: str
    execution_mode: str
    task: str
    fixture_ref: str
    seed: int | None
    readiness: str
    is_ready: bool
    created_at: datetime


class C2TestCaseDetailResponse(C2TestCaseSummaryResponse):
    definition: dict[str, Any]
    readiness_reasons: list[str]


class SuiteReadinessResponse(BaseModel):
    project_id: str
    suite_id: str
    total_cases: int
    ready_cases_count: int
    not_ready_cases_count: int
    readiness: str
    readiness_breakdown: dict[str, int]
    is_ready: bool


def _format_model_response(model) -> C2WorkflowModelResponse:
    return C2WorkflowModelResponse(
        id=model.id,
        project_id=model.project_id,
        model_id=model.model_id,
        version=model.version,
        schema_version=model.schema_version,
        name=model.name,
        description=model.description,
        content_hash=model.content_hash,
        lifecycle_status=model.lifecycle_status,
        approved_by=model.approved_by,
        approved_at=model.approved_at,
        review_basis=model.review_basis,
        review_notes=model.review_notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
        definition=model.definition,
    )


def _format_report_response(report) -> C2ValidationReportResponse:
    return C2ValidationReportResponse(
        id=report.id,
        model_record_id=report.model_record_id,
        project_id=report.project_id,
        model_id=report.model_id,
        version=report.version,
        content_hash=report.content_hash,
        is_valid=report.is_valid,
        readiness=report.readiness,
        summary=report.summary,
        errors=report.errors,
        warnings=report.warnings,
        diagnostics=report.diagnostics,
        created_at=report.created_at,
    )


def _format_suite_response(suite: C2TestSuite) -> C2TestSuiteResponse:
    return C2TestSuiteResponse(
        id=suite.id,
        project_id=suite.project_id,
        suite_id=suite.suite_id,
        model_id=suite.model_id,
        model_version=suite.model_version,
        model_content_hash=suite.model_content_hash,
        generator_version=suite.generator_version,
        seed=suite.seed,
        total_cases=suite.total_cases,
        ready_cases_count=suite.ready_cases_count,
        not_ready_cases_count=suite.not_ready_cases_count,
        category_counts=suite.category_counts,
        created_at=suite.created_at,
        config=suite.config,
        diagnostics=suite.diagnostics,
    )


def _format_case_response(case: C2TestCase) -> C2TestCaseDetailResponse:
    return C2TestCaseDetailResponse(
        id=case.id,
        project_id=case.project_id,
        suite_id=case.suite_id,
        test_id=case.test_id,
        category=case.category,
        execution_mode=case.execution_mode,
        task=case.task,
        fixture_ref=case.fixture_ref,
        seed=case.seed,
        readiness=case.readiness,
        is_ready=case.is_ready,
        created_at=case.created_at,
        definition=case.definition,
        readiness_reasons=case.readiness_reasons,
    )


# 1. Propose & Build candidate model
@router.post(
    "/projects/{project_id}/models/build",
    status_code=status.HTTP_201_CREATED,
    response_model=C2WorkflowModelResponse,
)
def build_and_propose_model(
    project_id: str,
    workflow_input: WorkflowInputContract,
    db: DbSession,
    auto_validate: Annotated[
        bool, Query(description="Automatically trigger validation after build")
    ] = True,
):
    if workflow_input.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route project_id '{project_id}' does not match payload project_id '{workflow_input.project_id}'.",
        )

    builder = DeterministicCandidateBuilder()
    try:
        model_def = builder.build_candidate_model(workflow_input)
    except InsufficientInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "diagnostics": exc.diagnostics},
        ) from exc

    repo = C2ModelRepository(db)
    try:
        model_record = repo.create_draft_model(project_id, model_def)
    except ModelAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if auto_validate:
        val_service = ModelValidationService(db)
        val_service.validate_model_record(
            project_id, model_record.model_id, model_record.version
        )
        db.refresh(model_record)

    return _format_model_response(model_record)


# 2. Directly create draft model
@router.post(
    "/projects/{project_id}/models",
    status_code=status.HTTP_201_CREATED,
    response_model=C2WorkflowModelResponse,
)
def create_model(
    project_id: str,
    model_definition: EFSMModelDefinition,
    db: DbSession,
):
    if model_definition.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route project_id '{project_id}' does not match definition project_id '{model_definition.project_id}'.",
        )

    repo = C2ModelRepository(db)
    try:
        record = repo.create_draft_model(project_id, model_definition)
    except ModelAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return _format_model_response(record)


# 3. List models for project
@router.get(
    "/projects/{project_id}/models",
    response_model=list[C2WorkflowModelSummaryResponse],
)
def list_models(
    project_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    models = repo.list_models(project_id)
    return [
        C2WorkflowModelSummaryResponse(
            id=m.id,
            project_id=m.project_id,
            model_id=m.model_id,
            version=m.version,
            schema_version=m.schema_version,
            name=m.name,
            description=m.description,
            content_hash=m.content_hash,
            lifecycle_status=m.lifecycle_status,
            approved_by=m.approved_by,
            approved_at=m.approved_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in models
    ]


# 4. Get specific model version
@router.get(
    "/projects/{project_id}/models/{model_id}/versions/{version}",
    response_model=C2WorkflowModelResponse,
)
def get_model(
    project_id: str,
    model_id: str,
    version: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    model = repo.get_model(project_id, model_id, version)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' version '{version}' not found for project '{project_id}'.",
        )
    return _format_model_response(model)


# 5. Validate model
@router.post(
    "/projects/{project_id}/models/{model_id}/versions/{version}/validate",
    response_model=C2ValidationReportResponse,
)
def validate_model(
    project_id: str,
    model_id: str,
    version: str,
    db: DbSession,
):
    val_service = ModelValidationService(db)
    try:
        report = val_service.validate_model_record(project_id, model_id, version)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return _format_report_response(report)


# 6. Retrieve validation reports
@router.get(
    "/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports",
    response_model=list[C2ValidationReportResponse],
)
def get_validation_reports(
    project_id: str,
    model_id: str,
    version: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    reports = repo.list_validation_reports(project_id, model_id, version)
    return [_format_report_response(r) for r in reports]


# 7. Record review and approval
@router.post(
    "/projects/{project_id}/models/{model_id}/versions/{version}/approve",
    response_model=C2WorkflowModelResponse,
)
def approve_model(
    project_id: str,
    model_id: str,
    version: str,
    request: ApprovalRequest,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    try:
        model = repo.approve_model(
            project_id=project_id,
            model_id=model_id,
            version=version,
            reviewer_id=f"{request.reviewer_id} [{request.review_type}]",
            review_basis=request.review_basis,
            review_notes=request.review_notes,
        )
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ApprovalBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return _format_model_response(model)


# 8. Create a new draft version
@router.post(
    "/projects/{project_id}/models/{model_id}/versions/{version}/new-draft",
    status_code=status.HTTP_201_CREATED,
    response_model=C2WorkflowModelResponse,
)
def create_new_draft(
    project_id: str,
    model_id: str,
    version: str,
    request: NewDraftVersionRequest,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    try:
        new_model = repo.create_new_draft_version(
            project_id=project_id,
            model_id=model_id,
            from_version=version,
            new_version=request.new_version,
            description=request.description,
        )
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return _format_model_response(new_model)


# 9. Check model readiness
@router.get(
    "/projects/{project_id}/models/{model_id}/versions/{version}/readiness",
    response_model=ModelReadinessResponse,
)
def check_readiness(
    project_id: str,
    model_id: str,
    version: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    model = repo.get_model(project_id, model_id, version)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' version '{version}' not found for project '{project_id}'.",
        )

    report = repo.get_latest_validation_report(project_id, model_id, version)
    reasons: list[str] = []
    validation_passed = False

    if report is None:
        reasons.append("Model has never been validated.")
    else:
        if report.content_hash != model.content_hash:
            reasons.append(
                "Validation report is stale (content hash mismatch with current definition)."
            )
        elif not report.is_valid:
            reasons.append(f"Validation failed with {len(report.errors)} error(s).")
        else:
            validation_passed = True

    is_approved = model.lifecycle_status == "APPROVED"
    if not is_approved:
        reasons.append("Model has not been explicitly reviewed and approved.")

    readiness = "READY" if (validation_passed and is_approved) else "MODEL NOT READY"

    return ModelReadinessResponse(
        project_id=project_id,
        model_id=model_id,
        version=version,
        lifecycle_status=model.lifecycle_status,
        readiness=readiness,
        is_approved=is_approved,
        content_hash=model.content_hash,
        validation_passed=validation_passed,
        reasons=reasons,
    )


# 10. Generate Test Suite
@router.post(
    "/projects/{project_id}/suites/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=C2TestSuiteResponse,
)
def generate_test_suite(
    project_id: str,
    request: GenerateTestSuiteRequest,
    db: DbSession,
):
    service = TestGenerationService(db)
    try:
        suite = service.generate_suite_for_model(
            project_id=project_id,
            model_id=request.model_id,
            version=request.version,
            request=request,
        )
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Model is not ready for test suite generation.",
                "readiness": "MODEL NOT READY",
                "reasons": exc.reasons,
            },
        ) from exc

    return _format_suite_response(suite)


# 11. List Test Suites
@router.get(
    "/projects/{project_id}/suites",
    response_model=list[C2TestSuiteSummaryResponse],
)
def list_test_suites(
    project_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    suites = repo.list_test_suites(project_id)
    return [
        C2TestSuiteSummaryResponse(
            id=s.id,
            project_id=s.project_id,
            suite_id=s.suite_id,
            model_id=s.model_id,
            model_version=s.model_version,
            model_content_hash=s.model_content_hash,
            generator_version=s.generator_version,
            seed=s.seed,
            total_cases=s.total_cases,
            ready_cases_count=s.ready_cases_count,
            not_ready_cases_count=s.not_ready_cases_count,
            category_counts=s.category_counts,
            created_at=s.created_at,
        )
        for s in suites
    ]


# 12. Get Specific Test Suite
@router.get(
    "/projects/{project_id}/suites/{suite_id}",
    response_model=C2TestSuiteResponse,
)
def get_test_suite(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )
    return _format_suite_response(suite)


# 13. List Cases in Suite
@router.get(
    "/projects/{project_id}/suites/{suite_id}/cases",
    response_model=list[C2TestCaseSummaryResponse],
)
def list_test_cases(
    project_id: str,
    suite_id: str,
    db: DbSession,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    readiness: Annotated[
        str | None, Query(description="Filter by readiness status")
    ] = None,
):
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )
    cases = repo.list_test_cases(
        project_id=project_id,
        suite_id=suite_id,
        category=category,
        readiness=readiness,
    )
    return [
        C2TestCaseSummaryResponse(
            id=c.id,
            project_id=c.project_id,
            suite_id=c.suite_id,
            test_id=c.test_id,
            category=c.category,
            execution_mode=c.execution_mode,
            task=c.task,
            fixture_ref=c.fixture_ref,
            seed=c.seed,
            readiness=c.readiness,
            is_ready=c.is_ready,
            created_at=c.created_at,
        )
        for c in cases
    ]


# 14. Get Specific Test Case Detail
@router.get(
    "/projects/{project_id}/suites/{suite_id}/cases/{test_id}",
    response_model=C2TestCaseDetailResponse,
)
def get_test_case_detail(
    project_id: str,
    suite_id: str,
    test_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    case = repo.get_test_case(project_id, suite_id, test_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{test_id}' not found in suite '{suite_id}'.",
        )
    return _format_case_response(case)


# 15. Check Suite Readiness
@router.get(
    "/projects/{project_id}/suites/{suite_id}/readiness",
    response_model=SuiteReadinessResponse,
)
def get_suite_readiness(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )

    diag = suite.diagnostics or {}
    readiness_breakdown = diag.get("readiness_breakdown", {})
    is_ready = suite.ready_cases_count > 0 and suite.not_ready_cases_count == 0
    readiness_status = "SUITE_READY" if is_ready else "SUITE_PARTIAL_OR_UNREADY"

    return SuiteReadinessResponse(
        project_id=project_id,
        suite_id=suite_id,
        total_cases=suite.total_cases,
        ready_cases_count=suite.ready_cases_count,
        not_ready_cases_count=suite.not_ready_cases_count,
        readiness=readiness_status,
        readiness_breakdown=readiness_breakdown,
        is_ready=is_ready,
    )


# 16. Export Full QA Suite (with reference paths, assertions, and mutations)
@router.get(
    "/projects/{project_id}/suites/{suite_id}/export/qa",
    response_model=QASuiteExport,
)
def export_qa_suite(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )
    cases = repo.list_test_cases(project_id, suite_id)
    return QASuiteExport(
        schema_version="2026.1",
        suite_id=suite.suite_id,
        project_id=suite.project_id,
        model_id=suite.model_id,
        model_version=suite.model_version,
        model_content_hash=suite.model_content_hash,
        generator_version=suite.generator_version,
        seed=suite.seed,
        created_at=suite.created_at,
        diagnostics=TestSuiteDiagnostics(**suite.diagnostics),
        cases=[GeneratedTestDefinition(**c.definition) for c in cases],
    )


# 17. Export Agent Task Payloads (Strict allowlist - NO reference paths or expected outcomes)
@router.get(
    "/projects/{project_id}/suites/{suite_id}/export/agent",
    response_model=list[AgentTaskPayload],
)
def export_agent_task_payloads(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )
    cases = repo.list_test_cases(project_id, suite_id)
    payloads: list[AgentTaskPayload] = []
    for c in cases:
        # Only supported agent-executable scenarios (LIVE_AGENT) may be exported
        if c.execution_mode != ExecutionMode.LIVE_AGENT.value:
            continue
        c_def = c.definition
        payloads.append(
            AgentTaskPayload(
                test_id=c.test_id,
                project_id=c.project_id,
                task=c.task,
                fixture_ref=c.fixture_ref,
                permitted_context=c_def.get("permitted_context", {}),
            )
        )
    return payloads


# 18. Individual Test Case Agent Payload (Strict allowlist)
@router.get(
    "/projects/{project_id}/suites/{suite_id}/cases/{test_id}/agent-payload",
    response_model=AgentTaskPayload,
)
def get_case_agent_payload(
    project_id: str,
    suite_id: str,
    test_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    case = repo.get_test_case(project_id, suite_id, test_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{test_id}' not found in suite '{suite_id}'.",
        )
    if case.execution_mode != ExecutionMode.LIVE_AGENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Test case '{test_id}' has execution mode '{case.execution_mode}' "
                "and cannot be exported for agent execution. Controlled synthetic evaluator mutants "
                "are excluded from agent-facing task payloads."
            ),
        )
    return AgentTaskPayload(
        test_id=case.test_id,
        project_id=case.project_id,
        task=case.task,
        fixture_ref=case.fixture_ref,
        permitted_context=case.definition.get("permitted_context", {}),
    )


# ---------------------------------------------------------------------------
# Part B: Conformance Evaluation and Synthetic Demonstration APIs
# ---------------------------------------------------------------------------


class DemonstrationRunRequest(BaseModel):
    """Configuration for running an offline synthetic demonstration."""

    scenario: str = Field(
        default="happy_path",
        description=(
            "Demonstration scenario: 'happy_path', 'inspection_alternative', 'unpaid_order_rejection', "
            "'skipped_step', 'reordered_step', 'repeated_step', 'wrong_entity', 'premature_termination', "
            "'missing_effect', 'protected_state_change', 'missing_observations', 'truncated_trace'"
        ),
    )
    model_id: str = "c2_refund_efsm_nexacart"
    model_version: str = "1.0.0"
    customer_id: int = 42
    target_order_id: int = 503


def _format_evaluation_response(record: C2EvaluationResult) -> EvaluationResultContract:
    cov_dict = record.coverage or {}
    summary_data = {
        k: v for k, v in cov_dict.items() if k in WorkflowCoverageSummary.model_fields
    }
    det_cov = None
    if "detailed_coverage" in cov_dict and isinstance(
        cov_dict["detailed_coverage"], dict
    ):
        try:
            det_cov = DetailedObservedCoverage(**cov_dict["detailed_coverage"])
        except (ValueError, TypeError, KeyError):
            det_cov = None

    return EvaluationResultContract(
        schema_version="2026.1",
        evaluation_id=record.id,
        project_id=record.project_id,
        suite_id=record.suite_id,
        test_id=record.test_id,
        run_id=record.run_id,
        evaluator_version=record.evaluator_version,
        verdict=RuntimeVerdict(record.verdict),
        reasons=record.reasons,
        model_id=record.model_id,
        model_version=record.model_version,
        model_content_hash=record.model_content_hash,
        expected_states=record.expected_states,
        observed_states=record.observed_states,
        violations=[ViolationDetail(**v) for v in record.violations],
        first_divergence=(
            FirstDivergenceDetail(**record.first_divergence)
            if record.first_divergence
            else None
        ),
        evidence_references=record.evidence_references,
        coverage=WorkflowCoverageSummary(**summary_data),
        detailed_coverage=det_cov,
        evaluator_timing_ms=record.evaluator_timing_ms,
        evaluated_at=record.created_at,
    )


# 19. Evaluate a Test Run from Runtime Evidence
@router.post(
    "/projects/{project_id}/suites/{suite_id}/cases/{test_id}/evaluate",
    response_model=EvaluationResultContract,
)
def evaluate_test_run(
    project_id: str,
    suite_id: str,
    test_id: str,
    evidence: RuntimeEvidenceContract,
    db: DbSession,
):
    if evidence.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route project_id '{project_id}' does not match evidence project_id '{evidence.project_id}'.",
        )
    if evidence.test_id != test_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route test_id '{test_id}' does not match evidence test_id '{evidence.test_id}'.",
        )

    service = WorkflowEvaluationService(db)
    try:
        return service.evaluate_test_run(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            evidence=evidence,
        )
    except TestCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictingEvidenceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


# 20. Retrieve Stored Evaluation Result
@router.get(
    "/projects/{project_id}/evaluations/{evaluation_id}",
    response_model=EvaluationResultContract,
)
def get_evaluation(
    project_id: str,
    evaluation_id: str,
    db: DbSession,
):
    repo = C2ModelRepository(db)
    record = repo.get_evaluation_result(project_id, evaluation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation result '{evaluation_id}' not found for project '{project_id}'.",
        )
    return _format_evaluation_response(record)


# 21. List Evaluation Results
@router.get(
    "/projects/{project_id}/evaluations",
    response_model=list[EvaluationResultContract],
)
def list_evaluations(
    project_id: str,
    db: DbSession,
    suite_id: str | None = None,
    test_id: str | None = None,
    verdict: str | None = None,
):
    repo = C2ModelRepository(db)
    records = repo.list_evaluation_results(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        verdict=verdict,
    )
    return [_format_evaluation_response(r) for r in records]


# 22. Clearly Labelled Synthetic Demonstration Runner
@router.post(
    "/projects/{project_id}/demonstrations/run",
    response_model=EvaluationResultContract,
)
def run_synthetic_demonstration(
    project_id: str,
    request: DemonstrationRunRequest,
    db: DbSession,
):
    """Execute a clearly labelled offline synthetic demonstration of C2 workflow evaluation."""
    repo = C2ModelRepository(db)
    model_record = repo.get_model(project_id, request.model_id, request.model_version)

    # Use built-in approved synthetic model if not found in DB
    if model_record is None:
        efsm_model = build_synthetic_refund_efsm()
        is_approved = True
        pinned_hash = "demonstration_hash"
    else:
        efsm_model = EFSMModelDefinition(**model_record.definition)
        is_approved = model_record.lifecycle_status == "APPROVED"
        pinned_hash = model_record.content_hash

    # Execute demonstration scenario
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    run_id = f"demo_run_{int(datetime.now().timestamp())}"
    test_id = f"demo_test_{request.scenario}"

    # Create dummy test definition representing the task
    is_neg = request.scenario == "unpaid_order_rejection"
    from app.components.c2_state_aware_workflow.contracts.test_definition import (
        ExpectedOutcomeType,
        TestCategory,
        TestReadinessStatus,
    )

    test_def = GeneratedTestDefinition(
        test_id=test_id,
        project_id=project_id,
        pinned_model_id=request.model_id,
        pinned_model_version=request.model_version,
        model_content_hash=pinned_hash,
        category=TestCategory.NEGATIVE if is_neg else TestCategory.VALID,
        task="Refund unpaid order 502" if is_neg else "Refund latest paid order 503",
        fixture_ref="fixture_demo",
        expected_outcome=(
            ExpectedOutcomeType.EXPECTED_REJECTION_PASS
            if is_neg
            else ExpectedOutcomeType.PASS
        ),
        readiness=TestReadinessStatus.TEST_READY,
    )

    # Branch according to scenario
    if request.scenario == "happy_path":
        evidence = agent.run_happy_path(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
    elif request.scenario == "inspection_alternative":
        evidence = agent.run_inspection_alternative(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
    elif request.scenario == "unpaid_order_rejection":
        evidence = agent.run_unpaid_order_rejection(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            unpaid_order_id=502,
        )
    elif request.scenario in (
        "skipped_step",
        "reordered_step",
        "repeated_step",
        "wrong_entity",
        "premature_termination",
    ):
        evidence = agent.run_flawed_demonstration(
            flaw_type=request.scenario,
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
    elif request.scenario == "missing_effect":
        base_ev = agent.run_happy_path(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
        evidence = ControlledTraceFixtures.create_missing_effect_trace(base_ev)
    elif request.scenario == "protected_state_change":
        base_ev = agent.run_unpaid_order_rejection(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            unpaid_order_id=502,
        )
        evidence = ControlledTraceFixtures.create_protected_state_change_trace(base_ev)
    elif request.scenario == "missing_observations":
        base_ev = agent.run_happy_path(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
        evidence = ControlledTraceFixtures.create_missing_observations_trace(base_ev)
    elif request.scenario == "truncated_trace":
        base_ev = agent.run_happy_path(
            project_id=project_id,
            test_id=test_id,
            run_id=run_id,
            model_id=request.model_id,
            model_version=request.model_version,
            customer_id=request.customer_id,
            target_order_id=request.target_order_id,
        )
        evidence = ControlledTraceFixtures.create_truncated_trace(base_ev)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown demonstration scenario '{request.scenario}'.",
        )

    # Evaluate
    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=efsm_model,
        test_def=test_def,
        evidence=evidence,
        model_is_approved=is_approved,
        pinned_content_hash=pinned_hash,
    )

    return result.model_copy(
        update={
            "project_id": project_id,
            "suite_id": "suite_demonstration",
            "run_id": run_id,
            "evaluation_id": f"eval_{run_id}",
        }
    )


# ---------------------------------------------------------------------------
# Day 3 Part A: Integration Orchestration, Coverage, and Reporting Endpoints
# ---------------------------------------------------------------------------


class SuiteRunRequest(BaseModel):
    max_cases: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum cases to execute in bounded suite run",
    )


class ReEvaluateRequest(BaseModel):
    evaluator_version: str | None = Field(
        default=None, description="Optional new evaluator version"
    )
    evaluator_config: dict[str, Any] | None = Field(
        default=None, description="Optional evaluator configuration override"
    )


# 23. Run a C2 Case with Orchestration Pipeline
@router.post(
    "/projects/{project_id}/suites/{suite_id}/cases/{test_id}/run",
    response_model=EvaluationResultContract,
)
def run_case_orchestration(
    project_id: str,
    suite_id: str,
    test_id: str,
    db: DbSession,
    run_id: str | None = None,
):
    """Run an isolated test case through fixture reset, runner, evidence collection, and evaluation."""
    service = C2IntegrationService(db)
    try:
        return service.run_case(project_id, suite_id, test_id, run_id=run_id)
    except TestCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictingEvidenceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


# 24. Run Bounded Test Suite
@router.post(
    "/projects/{project_id}/suites/{suite_id}/run",
    response_model=C2SuiteReportContract,
)
def run_suite_orchestration(
    project_id: str,
    suite_id: str,
    request: SuiteRunRequest,
    db: DbSession,
):
    """Execute a bounded batch of test cases for a suite and produce aggregate report."""
    repo = C2ModelRepository(db)
    suite = repo.get_test_suite(project_id, suite_id)
    if suite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test suite '{suite_id}' not found for project '{project_id}'.",
        )
    service = C2IntegrationService(db)
    return service.run_suite(project_id, suite_id, max_cases=request.max_cases)


# 25. Retrieve Retained Execution Evidence
@router.get(
    "/projects/{project_id}/evidence/{run_id}",
    response_model=dict[str, Any],
)
def get_retained_evidence(
    project_id: str,
    run_id: str,
    db: DbSession,
):
    """Retrieve original retained execution evidence, fixture snapshot, digest, and provenance."""
    repo = C2ModelRepository(db)
    evidence = repo.get_execution_evidence(project_id, run_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Retained evidence for run '{run_id}' not found in project '{project_id}'.",
        )
    return {
        "id": evidence.id,
        "project_id": evidence.project_id,
        "suite_id": evidence.suite_id,
        "test_id": evidence.test_id,
        "run_id": evidence.run_id,
        "evidence_digest": evidence.evidence_digest,
        "model_id": evidence.model_id,
        "model_version": evidence.model_version,
        "model_content_hash": evidence.model_content_hash,
        "execution_mode": evidence.execution_mode,
        "runner_id": evidence.runner_id,
        "runner_version": evidence.runner_version,
        "execution_provenance": evidence.execution_provenance,
        "evidence_payload": evidence.evidence_payload,
        "created_at": evidence.created_at,
    }


# 26. Reproducible Re-Evaluation
@router.post(
    "/projects/{project_id}/evaluations/{evaluation_id}/re-evaluate",
    response_model=EvaluationResultContract,
)
def re_evaluate_execution(
    project_id: str,
    evaluation_id: str,
    request: ReEvaluateRequest,
    db: DbSession,
):
    """Reproduce an evaluation from retained original evidence with optional new configuration/version."""
    service = WorkflowEvaluationService(db)
    try:
        return service.re_evaluate_execution(
            project_id=project_id,
            evaluation_id=evaluation_id,
            evaluator_version=request.evaluator_version,
            evaluator_config=request.evaluator_config,
        )
    except TestCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 26b. Verify Independent Replay Reproduction
@router.post(
    "/projects/{project_id}/evaluations/{evaluation_id}/verify-reproduction",
    response_model=ReproductionVerificationResult,
)
def verify_evaluation_reproduction(
    project_id: str,
    evaluation_id: str,
    db: DbSession,
):
    """Independently replays evaluation from retained raw evidence and verifies semantic equality."""
    service = WorkflowEvaluationService(db)
    try:
        return service.verify_execution_reproduction(
            project_id=project_id,
            evaluation_id=evaluation_id,
        )
    except TestCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 27. Retrieve Observed Coverage for a Single Run
@router.get(
    "/projects/{project_id}/evaluations/{evaluation_id}/coverage",
    response_model=DetailedObservedCoverage,
)
def get_evaluation_coverage(
    project_id: str,
    evaluation_id: str,
    db: DbSession,
):
    """Retrieve detailed observed coverage for a specific evaluation run."""
    report_service = C2ReportExportService(db)
    try:
        run_rep = report_service.build_run_report(project_id, evaluation_id)
        return run_rep.observed_coverage
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 28. Retrieve Aggregate Observed Coverage for a Suite
@router.get(
    "/projects/{project_id}/suites/{suite_id}/coverage",
    response_model=DetailedObservedCoverage,
)
def get_suite_coverage(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    """Retrieve aggregate observed workflow coverage across all evaluated runs in a suite."""
    report_service = C2ReportExportService(db)
    try:
        suite_rep = report_service.build_suite_report(project_id, suite_id)
        return suite_rep.aggregate_observed_coverage
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 29. Retrieve Per-Run C2 Report Contribution
@router.get(
    "/projects/{project_id}/evaluations/{evaluation_id}/report",
    response_model=C2ReportContributionContract,
)
def get_run_report(
    project_id: str,
    evaluation_id: str,
    db: DbSession,
):
    """Retrieve structured C2 report contribution for a single evaluation run."""
    report_service = C2ReportExportService(db)
    try:
        return report_service.build_run_report(project_id, evaluation_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 30. Retrieve Suite C2 Report Summary
@router.get(
    "/projects/{project_id}/suites/{suite_id}/report",
    response_model=C2SuiteReportContract,
)
def get_suite_report(
    project_id: str,
    suite_id: str,
    db: DbSession,
):
    """Retrieve aggregated C2 report for a test suite."""
    report_service = C2ReportExportService(db)
    try:
        return report_service.build_suite_report(project_id, suite_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 31. Export C2 Report Contribution
@router.post(
    "/projects/{project_id}/evaluations/{evaluation_id}/export-report",
    response_model=dict[str, Any],
)
def export_c2_report_contribution(
    project_id: str,
    evaluation_id: str,
    db: DbSession,
):
    """Export versioned C2 report contribution JSON and publish to reporting adapter."""
    report_service = C2ReportExportService(db)
    try:
        report = report_service.build_run_report(project_id, evaluation_id)
        publisher = C2ReportPublisher()
        pub_status = publisher.publish_component_finding(report)
        return {
            "evaluation_id": evaluation_id,
            "project_id": project_id,
            "published_to_shared_aggregator": False,
            "publishing_status": pub_status,
            "report_contribution": report.model_dump(mode="json"),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# C2 Part B: Experiments, Baselines, and Research Metrics APIs
# ---------------------------------------------------------------------------


class CreateExperimentRequest(BaseModel):
    """Request payload to configure and execute a comparative baseline experiment."""

    experiment_id: str
    name: str
    dataset_id: str
    dataset_version: str
    eval_methods: list[BaselineType] | None = None
    target_partition: DatasetPartition | None = None


# 32. Import and Validate Experiment Dataset Manifest
@router.post(
    "/projects/{project_id}/datasets",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
def import_experiment_dataset(
    project_id: str,
    manifest: ExperimentDatasetManifest,
    db: DbSession,
):
    """Import and persist a versioned, partition-isolated experiment dataset manifest."""
    if manifest.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manifest project_id '{manifest.project_id}' does not match route project_id '{project_id}'.",
        )
    repo = C2ModelRepository(db)
    try:
        record = repo.save_experiment_dataset(manifest)
        return {
            "dataset_id": record.dataset_id,
            "version": record.version,
            "name": record.name,
            "case_count": record.case_count,
            "development_count": record.development_count,
            "held_out_count": record.held_out_count,
            "is_frozen": record.is_frozen,
            "manifest_digest": record.manifest_digest,
            "created_at": record.created_at.isoformat(),
        }
    except ApprovedModelImmutableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


# 33. List Experiment Datasets
@router.get(
    "/projects/{project_id}/datasets",
    response_model=list[dict[str, Any]],
)
def list_experiment_datasets(
    project_id: str,
    db: DbSession,
):
    """List all versioned experiment datasets for a project."""
    repo = C2ModelRepository(db)
    records = repo.list_experiment_datasets(project_id)
    return [
        {
            "dataset_id": r.dataset_id,
            "version": r.version,
            "name": r.name,
            "case_count": r.case_count,
            "development_count": r.development_count,
            "held_out_count": r.held_out_count,
            "is_frozen": r.is_frozen,
            "manifest_digest": r.manifest_digest,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


# 34. Retrieve Experiment Dataset Manifest
@router.get(
    "/projects/{project_id}/datasets/{dataset_id}/versions/{version}",
    response_model=dict[str, Any],
)
def get_experiment_dataset(
    project_id: str,
    dataset_id: str,
    version: str,
    db: DbSession,
):
    """Retrieve full structured dataset manifest and case records."""
    repo = C2ModelRepository(db)
    record = repo.get_experiment_dataset(project_id, dataset_id, version)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} v{version} not found in project {project_id}.",
        )
    return record.manifest_payload


# 35. Freeze Experiment Dataset Manifest
@router.post(
    "/projects/{project_id}/datasets/{dataset_id}/versions/{version}/freeze",
    response_model=dict[str, Any],
)
def freeze_experiment_dataset(
    project_id: str,
    dataset_id: str,
    version: str,
    db: DbSession,
):
    """Freeze an experiment dataset manifest to lock partitions and labels."""
    repo = C2ModelRepository(db)
    try:
        record = repo.freeze_experiment_dataset(project_id, dataset_id, version)
        return {
            "dataset_id": record.dataset_id,
            "version": record.version,
            "is_frozen": record.is_frozen,
            "frozen_at": record.frozen_at.isoformat() if record.frozen_at else None,
            "manifest_digest": record.manifest_digest,
        }
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# 36. Create and Run Comparative Experiment
@router.post(
    "/projects/{project_id}/experiments",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
def create_and_run_experiment(
    project_id: str,
    request: CreateExperimentRequest,
    db: DbSession,
):
    """Execute baseline comparison (B1-B4) over retained frozen execution evidence."""
    repo = C2ModelRepository(db)
    dataset_rec = repo.get_experiment_dataset(
        project_id, request.dataset_id, request.dataset_version
    )
    if dataset_rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {request.dataset_id} v{request.dataset_version} not found.",
        )

    manifest = ExperimentDatasetManifest.model_validate(dataset_rec.manifest_payload)

    builder = BenchmarkSuiteBuilder(project_id=project_id)
    _, models_by_id, tests_by_id = builder.build_benchmark_manifest(
        dataset_id=manifest.dataset_id,
        name=manifest.name,
        version=manifest.version,
    )

    runner = ExperimentRunner()
    report, case_results = runner.run_experiment(
        experiment_id=request.experiment_id,
        experiment_name=request.name,
        manifest=manifest,
        models_by_id=models_by_id,
        tests_by_id=tests_by_id,
        eval_methods=request.eval_methods,
        target_partition=request.target_partition,
    )

    exp_record = C2Experiment(
        project_id=project_id,
        experiment_id=request.experiment_id,
        name=request.name,
        dataset_record_id=dataset_rec.id,
        dataset_id=request.dataset_id,
        dataset_version=request.dataset_version,
        status="COMPLETED",
        configuration=request.model_dump(mode="json"),
        results_summary=report.model_dump(mode="json"),
        completed_at=datetime.now(),
    )
    saved_exp = repo.create_or_update_experiment(exp_record)

    for cr in case_results:
        cr.experiment_record_id = saved_exp.id
    repo.save_experiment_case_results(case_results)

    return {
        "experiment_id": saved_exp.experiment_id,
        "name": saved_exp.name,
        "status": saved_exp.status,
        "total_cases_evaluated": len(case_results),
        "results_summary": report.model_dump(mode="json"),
    }


# 37. List Experiments
@router.get(
    "/projects/{project_id}/experiments",
    response_model=list[dict[str, Any]],
)
def list_experiments(
    project_id: str,
    dataset_id: str | None = None,
    db: DbSession = None,
):
    """List baseline comparison experiments for a project."""
    repo = C2ModelRepository(db)
    records = repo.list_experiments(project_id, dataset_id=dataset_id)
    return [
        {
            "experiment_id": r.experiment_id,
            "name": r.name,
            "dataset_id": r.dataset_id,
            "dataset_version": r.dataset_version,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in records
    ]


# 38. Retrieve Experiment Report and Baseline Comparisons
@router.get(
    "/projects/{project_id}/experiments/{experiment_id}/baselines",
    response_model=dict[str, Any],
)
def get_experiment_baseline_comparisons(
    project_id: str,
    experiment_id: str,
    db: DbSession,
):
    """Retrieve full comparative research metrics report across B1, B2, B3, and B4."""
    repo = C2ModelRepository(db)
    record = repo.get_experiment(project_id, experiment_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found in project '{project_id}'.",
        )
    return record.results_summary or {}


# 39. Retrieve Experiment Case Predictions
@router.get(
    "/projects/{project_id}/experiments/{experiment_id}/cases",
    response_model=list[dict[str, Any]],
)
def get_experiment_case_results(
    project_id: str,
    experiment_id: str,
    method_id: str | None = None,
    db: DbSession = None,
):
    """Retrieve fine-grained case prediction contracts and diagnostic records."""
    repo = C2ModelRepository(db)
    results = repo.get_experiment_case_results(
        project_id, experiment_id, method_id=method_id
    )
    return [
        {
            "case_id": r.case_id,
            "method_id": r.method_id,
            "partition": r.partition,
            "verdict": r.verdict,
            "is_violation": r.is_violation,
            "can_localize": r.can_localize,
            "first_divergence_predicted_step": r.first_divergence_predicted_step,
            "evaluator_timing_ms": r.evaluator_timing_ms,
            "evidence_digest_consumed": r.evidence_digest_consumed,
            "result_payload": r.result_payload,
        }
        for r in results
    ]


# 40. Export Experiment Metrics (JSON or CSV)
@router.get(
    "/projects/{project_id}/experiments/{experiment_id}/export",
    response_model=dict[str, Any],
)
def export_experiment_metrics(
    project_id: str,
    experiment_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: DbSession = None,
):
    """Export benchmark comparison metrics in JSON or summary CSV format."""
    repo = C2ModelRepository(db)
    record = repo.get_experiment(project_id, experiment_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found.",
        )
    summary = record.results_summary or {}

    if format == "csv":
        lines = [
            "method,partition,precision,recall,f1_score,localization_accuracy,mutation_detection,state_fault_detection,overhead_median_ms,overhead_p95_ms"
        ]
        methods_dict = summary.get("metrics_by_method", {})
        for m_id, m_data in methods_dict.items():
            det = m_data.get("detection_metrics", {})
            loc = m_data.get("localization_metrics", {})
            lines.append(
                f"{m_id},{m_data.get('partition')},{det.get('precision')},{det.get('recall')},{det.get('f1_score')},"
                f"{loc.get('accuracy')},{det.get('mutation_detection_score')},{det.get('state_effect_fault_detection_score')},"
                f"{m_data.get('overhead_median_ms')},{m_data.get('overhead_p95_ms')}"
            )
        csv_content = "\n".join(lines)
        return Response(content=csv_content, media_type="text/csv")

    return summary
