"""Persistence, retrieval, and reporting API router for Component 3 Phase 5.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.api.authorization import (
    require_c3_active_user,
    verify_c3_project_access,
    verify_project_consistency,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    CaseRecordResponse,
    ControlledExecutionRequest,
    ControlledExecutionResponse,
    EvaluationComputeRequest,
    EvaluationRecordResponse,
    ExecutionArtifactImportRequest,
    ExecutionCreateRequest,
    ExecutionRecordResponse,
    MatchedPairImportRequest,
    MatchedPairRecordResponse,
    PaginatedResponse,
    SuiteImportRequest,
    SuiteRecordResponse,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    ConflictError,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import SuiteRunner
from app.components.c3_robustness_recovery.services.reporting import (
    build_execution_report,
    export_report_to_csv,
)
from app.components.c3_robustness_recovery.services.run_tracking import (
    create_execution_manifest,
    finalize_execution_lifecycle,
    get_execution as service_get_execution,
    import_execution_artifact,
    list_executions as service_list_executions,
    record_case_execution_progress,
)
from app.components.c3_robustness_recovery.services.suites import (
    verify_suite_integrity,
)
from app.components.c3_robustness_recovery.services.storage import (
    compute_and_store_evaluation,
    store_frozen_suite,
    store_matched_pair,
)
from app.components.c3_robustness_recovery.services.storage import (
    get_case as service_get_case,
)
from app.components.c3_robustness_recovery.services.storage import (
    get_evaluation as service_get_evaluation,
)
from app.components.c3_robustness_recovery.services.storage import (
    get_matched_pair as service_get_matched_pair,
)
from app.components.c3_robustness_recovery.services.storage import (
    get_suite as service_get_suite,
)
from app.components.c3_robustness_recovery.services.storage import (
    list_cases as service_list_cases,
)
from app.components.c3_robustness_recovery.services.storage import (
    list_evaluations as service_list_evaluations,
)
from app.components.c3_robustness_recovery.services.storage import (
    list_matched_pairs as service_list_matched_pairs,
)
from app.components.c3_robustness_recovery.services.storage import (
    list_suites as service_list_suites,
)
from app.database import get_db
from app.shared.auth.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Suites Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/suites/import",
    response_model=SuiteRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Import Verified Frozen Suite",
    description="Idempotently validates and persists a frozen suite and its candidate cases.",
)
def import_suite_endpoint(
    request: SuiteImportRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuiteRecordResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    for case in request.frozen_suite.selected_cases:
        verify_project_consistency(request.project_id, getattr(case, "project_id", None))
    try:
        return store_frozen_suite(db, request.project_id, request.frozen_suite)
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/suites",
    response_model=PaginatedResponse[SuiteRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List Stored Frozen Suites",
)
def list_suites_endpoint(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    domain: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[SuiteRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return service_list_suites(
            db, project_id=project_id, domain=domain, limit=limit, offset=offset
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/suites/{suite_id_or_digest}",
    response_model=SuiteRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Stored Frozen Suite",
)
def get_suite_endpoint(
    suite_id_or_digest: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuiteRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        suite = service_get_suite(db, project_id, suite_id_or_digest)
        if not suite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suite '{suite_id_or_digest}' not found in project '{project_id}'.",
            )
        return suite
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


# ---------------------------------------------------------------------------
# Cases Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/cases",
    response_model=PaginatedResponse[CaseRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List Stored Candidate Cases",
)
def list_cases_endpoint(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    suite_digest: str | None = None,
    fault_family: str | None = None,
    effect_phase: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[CaseRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return service_list_cases(
            db,
            project_id=project_id,
            suite_digest=suite_digest,
            fault_family=fault_family,
            effect_phase=effect_phase,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/cases/{case_id}",
    response_model=CaseRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Stored Candidate Case Snapshot",
)
def get_case_endpoint(
    case_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    suite_digest: str | None = None,
) -> CaseRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        case = service_get_case(
            db, project_id=project_id, case_id=case_id, suite_digest=suite_digest
        )
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{case_id}' not found in project '{project_id}'.",
            )
        return case
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


# ---------------------------------------------------------------------------
# Executions / Runs Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/executions/import",
    response_model=ExecutionRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Import Execution Artifact",
    description="Transactionally persist a completed or partial execution artifact without target execution.",
)
def import_execution_endpoint(
    request: ExecutionArtifactImportRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutionRecordResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    for ev in request.case_evidences:
        verify_project_consistency(request.project_id, getattr(ev, "project_id", None))
    try:
        return import_execution_artifact(db, request)
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.post(
    "/executions/run-controlled",
    response_model=ControlledExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Controlled Trials for Stored Suite",
    description="Launches native SuiteRunner under registered demonstration adapter with full evidence retention.",
)
async def run_controlled_trials_endpoint(
    request: ControlledExecutionRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ControlledExecutionResponse:
    verify_c3_project_access(request.project_id, current_user, db)

    # 1. Enforce target mode safeguards
    if request.execution_mode == "LIVE_AUT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "LIVE_AUT execution mode is BLOCKED: Live NexaCart adapter connector is not implemented. "
                "Only registered DEMONSTRATION mode is supported."
            ),
        )
    if request.execution_mode != "DEMONSTRATION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported execution mode '{request.execution_mode}'. Only DEMONSTRATION is supported.",
        )

    # 2. Retrieve referenced stored frozen suite
    suite_record = service_get_suite(db, request.project_id, request.suite_id_or_digest)
    if not suite_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite '{request.suite_id_or_digest}' not found in project '{request.project_id}'.",
        )

    frozen_suite = suite_record.frozen_suite

    # 3. Verify suite integrity
    try:
        verify_suite_integrity(frozen_suite)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Suite integrity verification failed: {exc}",
        ) from exc

    # 4. Resolve registered installed adapter and fixture manager
    fixture_manager = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager)

    # 5. Persist execution intent before target activity starts
    exec_create_req = ExecutionCreateRequest(
        suite_digest=suite_record.suite_digest,
        project_id=request.project_id,
        target_mode=request.execution_mode,
        caller_identity="SCRIPTED_CALLER",
        planned_cases=[c.case_id for c in frozen_suite.selected_cases],
        configuration_snapshot={
            "adapter_id": adapter.adapter_id,
            "adapter_version": adapter.adapter_version,
            "fixture_id": fixture_manager.fixture_id,
            "fixture_version": fixture_manager.fixture_version,
            "target_mode": request.execution_mode,
            "max_suite_duration_sec": request.max_suite_duration_sec,
            "per_case_timeout_sec": request.per_case_timeout_sec,
        },
    )
    try:
        manifest_record = create_execution_manifest(db, request.project_id, exec_create_req)
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    # 6. Execute suite sequentially with isolated fixtures and strict bounds
    suite_runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=fixture_manager,
        task_fixture_metadata=frozen_suite.task_fixture_metadata,
        recovery_contract=frozen_suite.recovery_contract,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        max_suite_duration_sec=request.max_suite_duration_sec,
        per_case_timeout_sec=request.per_case_timeout_sec,
    )
    summary = await suite_runner.run_frozen_suite(frozen_suite)

    # 7. Persist execution progress, matched pairs evidence, and finalize lifecycle
    pair_ids: list[str] = []
    case_results: list[dict[str, Any]] = []

    for res in summary.case_results:
        pair_id = res.evidence.pair_id if res.evidence else None
        if pair_id:
            pair_ids.append(pair_id)

        record_case_execution_progress(
            db=db,
            project_id=request.project_id,
            execution_id=manifest_record.execution_id,
            case_id=res.case_id,
            status=res.status,
            evidence=res.evidence,
        )

        exposure_str = (
            res.evidence.exposure_status.value
            if res.evidence and hasattr(res.evidence.exposure_status, "value")
            else str(res.evidence.exposure_status) if res.evidence else None
        )

        case_results.append({
            "case_id": res.case_id,
            "status": res.status,
            "pair_id": pair_id,
            "duration_ms": res.duration_ms,
            "blocked_reasons": res.blocked_reasons,
            "exposure_status": exposure_str,
        })

    final_exec = finalize_execution_lifecycle(
        db=db,
        project_id=request.project_id,
        execution_id=manifest_record.execution_id,
        summary=summary,
    )

    return ControlledExecutionResponse(
        execution_id=final_exec.execution_id,
        suite_id=suite_record.suite_id,
        suite_digest=suite_record.suite_digest,
        project_id=request.project_id,
        target_mode=request.execution_mode,
        status=final_exec.status.value if hasattr(final_exec.status, "value") else str(final_exec.status),
        total_cases=len(frozen_suite.selected_cases),
        executed_cases=summary.executed_count,
        blocked_cases=summary.blocked_count,
        unsupported_cases=summary.unsupported_count,
        confirmed_exposure_count=summary.confirmed_exposure_count,
        not_triggered_exposure_count=summary.not_triggered_count,
        unknown_exposure_count=summary.unknown_exposure_count,
        pair_ids=pair_ids,
        halt_reason=summary.halt_reason,
        case_results=case_results,
    )


@router.get(
    "/executions",
    response_model=PaginatedResponse[ExecutionRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tracked Executions",
)
def list_executions_endpoint(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    suite_digest: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    target_mode: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[ExecutionRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return service_list_executions(
            db,
            project_id=project_id,
            suite_digest=suite_digest,
            status=status_filter,
            target_mode=target_mode,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tracked Execution Status",
)
def get_execution_endpoint(
    execution_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutionRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        exec_record = service_get_execution(db, project_id, execution_id)
        if not exec_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found in project '{project_id}'.",
            )
        return exec_record
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


# ---------------------------------------------------------------------------
# Matched Pairs Evidence Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/pairs/import",
    response_model=MatchedPairRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Import Matched Pair Evidence",
    description="Validate and idempotently persist matched clean/fault trial pair evidence.",
)
def import_pair_endpoint(
    request: MatchedPairImportRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MatchedPairRecordResponse:
    verify_project_consistency(request.project_id, request.evidence.project_id)
    verify_c3_project_access(request.project_id, current_user, db)
    try:
        return store_matched_pair(
            db,
            project_id=request.project_id,
            evidence=request.evidence,
            execution_id=request.execution_id,
        )
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/pairs",
    response_model=PaginatedResponse[MatchedPairRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List Matched Trial Pairs",
)
def list_pairs_endpoint(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    execution_id: str | None = None,
    case_id: str | None = None,
    run_id: str | None = None,
    exposure_status: str | None = None,
    clean_qualification: str | None = None,
    fault_execution_status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[MatchedPairRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return service_list_matched_pairs(
            db,
            project_id=project_id,
            execution_id=execution_id,
            case_id=case_id,
            run_id=run_id,
            exposure_status=exposure_status,
            clean_qualification=clean_qualification,
            fault_execution_status=fault_execution_status,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/pairs/{pair_id}",
    response_model=MatchedPairRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Matched Pair Evidence Record",
)
def get_pair_endpoint(
    pair_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MatchedPairRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        pair = service_get_matched_pair(db, project_id, pair_id)
        if not pair:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matched pair '{pair_id}' not found in project '{project_id}'.",
            )
        return pair
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


# ---------------------------------------------------------------------------
# Recovery Evaluations Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/evaluations/compute",
    response_model=EvaluationRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute and Store Recovery Evaluation",
    description="Loads referenced evidence/contracts and executes the authoritative evaluation engine.",
)
def compute_evaluation_endpoint(
    request: EvaluationComputeRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationRecordResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    try:
        return compute_and_store_evaluation(db, request)
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/evaluations",
    response_model=PaginatedResponse[EvaluationRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List Stored Recovery Evaluations",
)
def list_evaluations_endpoint(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    pair_id: str | None = None,
    case_id: str | None = None,
    recovery_verdict: str | None = None,
    evaluator_version: str | None = None,
    rule_set_version: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[EvaluationRecordResponse]:
    verify_c3_project_access(project_id, current_user, db)
    try:
        return service_list_evaluations(
            db,
            project_id=project_id,
            pair_id=pair_id,
            case_id=case_id,
            recovery_verdict=recovery_verdict,
            evaluator_version=evaluator_version,
            rule_set_version=rule_set_version,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Stored Recovery Evaluation Result",
)
def get_evaluation_endpoint(
    evaluation_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationRecordResponse:
    verify_c3_project_access(project_id, current_user, db)
    try:
        res = service_get_evaluation(db, project_id, evaluation_id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation '{evaluation_id}' not found in project '{project_id}'.",
            )
        return res
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


# ---------------------------------------------------------------------------
# Reports Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/reports/executions/{execution_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Structured Execution Report",
    description="Returns comprehensive execution summary and recovery evaluation metrics with explicit denominators.",
)
def get_execution_report_endpoint(
    execution_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    verify_c3_project_access(project_id, current_user, db)
    try:
        return build_execution_report(db, project_id, execution_id)
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc


@router.get(
    "/reports/executions/{execution_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Download Execution Report as CSV",
    description="Downloads execution metrics and per-case results formatted as CSV.",
)
def export_execution_report_csv_endpoint(
    execution_id: str,
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    verify_c3_project_access(project_id, current_user, db)
    try:
        report = build_execution_report(db, project_id, execution_id)
        csv_data = export_report_to_csv(report)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="report_{execution_id}.csv"'
            },
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from exc
