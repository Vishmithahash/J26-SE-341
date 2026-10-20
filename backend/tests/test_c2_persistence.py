"""Tests for C2 persistence, deterministic hashing, version isolation, and approval lifecycle."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    FinalOutcome,
    StateDefinition,
    StateType,
    TransitionDefinition,
)
from app.components.c2_state_aware_workflow.persistence import (
    ApprovalBlockedError,
    ApprovedModelImmutableError,
    C2ModelRepository,
    compute_model_content_hash,
)
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


def create_sample_efsm(
    project_id="proj_1", model_id="m1", version="1.0.0"
) -> EFSMModelDefinition:
    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id=model_id,
        version=version,
        name="Sample EFSM",
        states=[
            StateDefinition(id="START", name="Start", type=StateType.INITIAL),
            StateDefinition(id="DONE", name="Done", type=StateType.TERMINAL_ACCEPTING),
        ],
        initial_state_id="START",
        accepting_state_ids=["DONE"],
        transitions=[
            TransitionDefinition(
                id="T1",
                source_state="START",
                target_state="DONE",
                trigger_event="finish",
            )
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="DONE",
                description="Done",
            )
        ],
    )


def test_deterministic_hashing():
    model1 = create_sample_efsm()
    hash1 = compute_model_content_hash(model1)

    # Identical definition produces identical hash
    model2 = create_sample_efsm()
    hash2 = compute_model_content_hash(model2)
    assert hash1 == hash2

    # Changing behavioral rules/transitions alters hash
    model3_dict = model1.model_dump()
    model3_dict["transitions"][0]["trigger_event"] = "finish_modified"
    hash3 = compute_model_content_hash(model3_dict)
    assert hash1 != hash3

    # Excluded metadata fields do not alter hash
    model1_dict = model1.model_dump()
    model1_dict["created_at"] = "2026-10-18T10:00:00Z"
    model1_dict["approved_by"] = "reviewer_alice"
    assert compute_model_content_hash(model1_dict) == hash1


def test_model_creation_and_project_isolation(db_session: Session):
    repo = C2ModelRepository(db_session)
    model_a = create_sample_efsm(
        project_id="project_A", model_id="refund", version="1.0.0"
    )
    model_b = create_sample_efsm(
        project_id="project_B", model_id="refund", version="1.0.0"
    )

    rec_a = repo.create_draft_model("project_A", model_a)
    rec_b = repo.create_draft_model("project_B", model_b)

    assert rec_a.lifecycle_status == "DRAFT"
    assert rec_b.lifecycle_status == "DRAFT"

    # Isolation check: fetching from project_A returns rec_a, not rec_b
    fetched_a = repo.get_model("project_A", "refund", "1.0.0")
    assert fetched_a is not None
    assert fetched_a.id == rec_a.id

    fetched_b = repo.get_model("project_B", "refund", "1.0.0")
    assert fetched_b is not None
    assert fetched_b.id == rec_b.id

    # Non-existent in project_C
    assert repo.get_model("project_C", "refund", "1.0.0") is None


def test_approval_blocked_without_validation(db_session: Session):
    repo = C2ModelRepository(db_session)
    model = create_sample_efsm()
    repo.create_draft_model("proj_1", model)

    with pytest.raises(ApprovalBlockedError) as exc_info:
        repo.approve_model(
            "proj_1", "m1", "1.0.0", reviewer_id="qa_lead", review_basis="Spec v1"
        )
    assert "model has not passed structural and semantic validation" in str(
        exc_info.value
    )


def test_approval_blocked_on_stale_validation(db_session: Session):
    repo = C2ModelRepository(db_session)
    model = create_sample_efsm()
    repo.create_draft_model("proj_1", model)

    val_service = ModelValidationService(db_session)
    val_service.validate_model_record("proj_1", "m1", "1.0.0")

    # Modify draft definition (changes content hash)
    updated_def = model.model_dump()
    updated_def["name"] = "Updated Name"
    updated_def["transitions"][0]["description"] = "New description"
    repo.update_draft_model("proj_1", "m1", "1.0.0", updated_def)

    # Attempting to approve now is blocked because previous validation report is stale
    with pytest.raises(ApprovalBlockedError) as exc_info:
        repo.approve_model(
            "proj_1", "m1", "1.0.0", reviewer_id="qa_lead", review_basis="Spec v1"
        )
    assert "validation report is stale" in str(exc_info.value)


def test_successful_approval_and_immutability(db_session: Session):
    repo = C2ModelRepository(db_session)
    model = create_sample_efsm()
    repo.create_draft_model("proj_1", model)

    val_service = ModelValidationService(db_session)
    val_report = val_service.validate_model_record("proj_1", "m1", "1.0.0")
    assert val_report.is_valid is True

    # Approve
    approved_model = repo.approve_model(
        project_id="proj_1",
        model_id="m1",
        version="1.0.0",
        reviewer_id="lead_qa_alice [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Validated against formal requirements document",
        review_notes="All structural and bounded reachability checks passed cleanly.",
    )
    assert approved_model.lifecycle_status == "APPROVED"
    assert approved_model.approved_by == "lead_qa_alice [SELF_REPORTED_DEVELOPMENT]"
    assert approved_model.approved_at is not None

    # Verify immutability: attempting to edit approved version raises error
    with pytest.raises(ApprovedModelImmutableError) as exc_info:
        repo.update_draft_model("proj_1", "m1", "1.0.0", model)
    assert "is APPROVED and immutable" in str(exc_info.value)


def test_new_draft_version_creation(db_session: Session):
    repo = C2ModelRepository(db_session)
    model = create_sample_efsm()
    repo.create_draft_model("proj_1", model)

    val_service = ModelValidationService(db_session)
    val_service.validate_model_record("proj_1", "m1", "1.0.0")
    repo.approve_model(
        "proj_1", "m1", "1.0.0", reviewer_id="lead_qa", review_basis="Spec"
    )

    # Create new draft version 1.1.0 from approved 1.0.0
    new_draft = repo.create_new_draft_version(
        project_id="proj_1",
        model_id="m1",
        from_version="1.0.0",
        new_version="1.1.0",
        description="Iterating on refund workflow",
    )
    assert new_draft.version == "1.1.0"
    assert new_draft.lifecycle_status == "DRAFT"
    assert new_draft.approved_by is None
    assert new_draft.approved_at is None
