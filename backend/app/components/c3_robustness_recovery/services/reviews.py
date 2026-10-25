"""Append-only human review of stored C3 recovery evaluations.

Component: C3 - Robustness and Failure Recovery Testing

The deterministic evaluation is never changed. A reviewer (for example on an INCONCLUSIVE result)
records their own verdict, whether the evidence was sufficient, and why. These are the proposal's
independent reviewer labels; several reviewers may label the same evaluation.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.evaluation import RecoveryVerdict
from app.components.c3_robustness_recovery.models.persistence import (
    C3EvaluationModel,
    C3EvaluationReviewModel,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    EntityNotFoundError,
)
from app.shared.auth.models import User


class EvaluationReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    reviewer_verdict: RecoveryVerdict
    evidence_sufficient: bool
    rationale: str = Field(..., min_length=10, max_length=2000)


class EvaluationReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    evaluation_id: str
    pair_id: str
    project_id: str
    evaluator_verdict: str | None
    reviewer_verdict: str
    agrees_with_evaluator: bool
    evidence_sufficient: bool
    rationale: str
    reviewer_name: str | None = None
    reviewer_email: str
    created_at_utc: str


def _reviewer_names(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all()
    return {row.id: row.name for row in rows}


def _to_response(
    model: C3EvaluationReviewModel, reviewer_name: str | None = None
) -> EvaluationReviewResponse:
    return EvaluationReviewResponse(
        review_id=model.review_id,
        evaluation_id=model.evaluation_id,
        pair_id=model.pair_id,
        project_id=model.project_id,
        evaluator_verdict=model.evaluator_verdict,
        reviewer_verdict=model.reviewer_verdict,
        agrees_with_evaluator=model.reviewer_verdict == model.evaluator_verdict,
        evidence_sufficient=model.evidence_sufficient,
        rationale=model.rationale,
        reviewer_name=reviewer_name,
        reviewer_email=model.reviewer_email,
        created_at_utc=model.created_at_utc.isoformat(),
    )


def create_review(
    db: Session,
    evaluation_id: str,
    request: EvaluationReviewCreateRequest,
    reviewer_user_id: int,
    reviewer_email: str,
) -> EvaluationReviewResponse:
    evaluation = db.scalars(
        select(C3EvaluationModel).where(
            C3EvaluationModel.project_id == request.project_id,
            C3EvaluationModel.evaluation_id == evaluation_id,
        )
    ).first()
    if evaluation is None:
        raise EntityNotFoundError(
            f"Evaluation '{evaluation_id}' not found in project '{request.project_id}'."
        )
    model = C3EvaluationReviewModel(
        review_id=f"review-{uuid4().hex[:12]}",
        evaluation_id=evaluation.evaluation_id,
        pair_id=evaluation.pair_id,
        project_id=evaluation.project_id,
        evaluator_verdict=evaluation.recovery_verdict,
        reviewer_verdict=request.reviewer_verdict.value,
        evidence_sufficient=request.evidence_sufficient,
        rationale=request.rationale.strip(),
        reviewer_user_id=reviewer_user_id,
        reviewer_email=reviewer_email,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    names = _reviewer_names(db, {reviewer_user_id})
    return _to_response(model, names.get(reviewer_user_id))


def list_reviews(
    db: Session, project_id: str, evaluation_id: str | None = None
) -> list[EvaluationReviewResponse]:
    query = select(C3EvaluationReviewModel).where(
        C3EvaluationReviewModel.project_id == project_id
    )
    if evaluation_id:
        query = query.where(C3EvaluationReviewModel.evaluation_id == evaluation_id)
    models = db.scalars(
        query.order_by(C3EvaluationReviewModel.created_at_utc.desc())
    ).all()
    names = _reviewer_names(db, {m.reviewer_user_id for m in models})
    return [_to_response(m, names.get(m.reviewer_user_id)) for m in models]
