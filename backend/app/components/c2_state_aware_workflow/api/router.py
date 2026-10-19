"""FastAPI router for C2: State-Aware Multi-Step Workflow Testing APIs."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
    InsufficientInputError,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    ApprovalBlockedError,
    C2ModelRepository,
    ModelAlreadyExistsError,
    ModelNotFoundError,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import get_db

router = APIRouter(prefix="/api/v1/c2", tags=["c2-state-aware-workflow"])
DbSession = Annotated[Session, Depends(get_db)]


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
