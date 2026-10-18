"""Tests demonstrating proposal, validation, and approval of the synthetic refund example."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    get_refund_workflow_input,
)
from app.components.c2_state_aware_workflow.persistence import C2ModelRepository
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_synthetic_refund_efsm_validation_and_approval_lifecycle(db_session: Session):
    # 1. Propose / Load reference refund model
    efsm = build_synthetic_refund_efsm()
    assert efsm.project_id == "research_project_nexacart"
    assert efsm.model_id == "refund_efsm"
    assert efsm.version == "1.0.0"
    assert efsm.initial_state_id == "START"
    assert "REFUNDED" in efsm.accepting_state_ids
    assert "REJECTED_UNPAID" in efsm.rejection_state_ids

    # Verify states and alternative path presence
    state_ids = {s.id for s in efsm.states}
    assert "ORDER_DETAILS_INSPECTED" in state_ids
    assert "REFUNDED" in state_ids
    assert "REJECTED_UNPAID" in state_ids

    # 2. Persist as DRAFT in repository
    repo = C2ModelRepository(db_session)
    record = repo.create_draft_model(efsm.project_id, efsm)
    assert record.lifecycle_status == "DRAFT"

    # 3. Validate model
    val_service = ModelValidationService(db_session)
    report = val_service.validate_model_record(
        efsm.project_id, efsm.model_id, efsm.version
    )

    assert report.is_valid is True
    assert report.readiness == "READY"
    assert report.errors == []
    # Verify alternative paths detected during bounded semantic validation
    assert report.diagnostics["alternative_paths_identified"] >= 1
    assert report.diagnostics["guards_checked"] > 0
    assert report.diagnostics["invariants_checked"] > 0

    # Model promoted to VALIDATED
    db_session.refresh(record)
    assert record.lifecycle_status == "VALIDATED"

    # 4. Explicit review and approval
    approved = repo.approve_model(
        project_id=efsm.project_id,
        model_id=efsm.model_id,
        version=efsm.version,
        reviewer_id="researcher_dasith [SELF_REPORTED_DEVELOPMENT]",
        review_basis="NexaCart synthetic refund requirements and Appendix A specification",
        review_notes="Verified customer 42, latest order 503 selection, unpaid 502 rejection, and protected state.",
    )
    assert approved.lifecycle_status == "APPROVED"
    assert approved.approved_by == "researcher_dasith [SELF_REPORTED_DEVELOPMENT]"
    assert approved.approved_at is not None


def test_synthetic_refund_candidate_builder(db_session: Session):
    # Demonstrate deterministic candidate builder on the refund workflow input
    workflow_input = get_refund_workflow_input()
    builder = DeterministicCandidateBuilder()
    candidate_model = builder.build_candidate_model(workflow_input)

    assert candidate_model.project_id == "research_project_nexacart"
    assert candidate_model.model_id == "order_refund_workflow"
    assert candidate_model.initial_state_id == "START"
    assert "COMPLETED" in candidate_model.accepting_state_ids
    assert "REJECTED" in candidate_model.rejection_state_ids

    # Validate the generated candidate model
    val_service = ModelValidationService(db_session)
    is_valid, readiness, _summary, errors, _warnings, _diag = (
        val_service.validate_definition(candidate_model)
    )
    assert is_valid is True
    assert readiness == "READY"
    assert errors == []
