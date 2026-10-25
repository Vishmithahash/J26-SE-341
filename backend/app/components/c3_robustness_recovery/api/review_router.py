"""Reviewer labels for stored C3 recovery evaluations.

Component: C3 - Robustness and Failure Recovery Testing
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.api.authorization import (
    require_c3_active_user,
    verify_c3_project_access,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.services.reviews import (
    EvaluationReviewCreateRequest,
    EvaluationReviewResponse,
    create_review,
    list_reviews,
)
from app.database import get_db
from app.shared.auth.models import User

router = APIRouter()


@router.post(
    "/evaluations/{evaluation_id}/reviews",
    response_model=EvaluationReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a Reviewer Verdict for an Evaluation",
    description=(
        "Appends a human review (verdict, evidence sufficiency, rationale) next to a stored "
        "evaluation. The deterministic evaluation itself is never changed."
    ),
)
def create_evaluation_review(
    evaluation_id: str,
    request: EvaluationReviewCreateRequest,
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationReviewResponse:
    verify_c3_project_access(request.project_id, current_user, db)
    try:
        return create_review(
            db, evaluation_id, request, current_user.id, current_user.email
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/reviews",
    response_model=list[EvaluationReviewResponse],
    summary="List Reviewer Verdicts",
)
def list_evaluation_reviews(
    project_id: Annotated[str, Query(..., min_length=1)],
    current_user: Annotated[User, Depends(require_c3_active_user)],
    db: Annotated[Session, Depends(get_db)],
    evaluation_id: str | None = None,
) -> list[EvaluationReviewResponse]:
    verify_c3_project_access(project_id, current_user, db)
    return list_reviews(db, project_id, evaluation_id)
