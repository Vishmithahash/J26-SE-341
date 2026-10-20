"""Regression tests for Day 1 gaps and architectural invariants.

Gaps fixed:
1. Separate 'Refund my latest paid order' from 'Refund unpaid order 502'.
   Rejecting order 502 must not satisfy the latest-paid-order task when eligible order 503 exists.
2. Treat bounded validation limits as unresolved checks rather than proof of infeasibility or unreachability.
3. Preserve project/version isolation, hash-linked validation, and approved-model immutability.
"""

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
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GenerateTestSuiteRequest,
    TestCategory,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    build_synthetic_unpaid_order_rejection_efsm,
)
from app.components.c2_state_aware_workflow.generator.engine import (
    CoverageGuidedGenerator,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ModelAlreadyExistsError,
)
from app.components.c2_state_aware_workflow.validator.semantic import (
    BoundedSemanticValidator,
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


def test_regression_rejecting_unpaid_order_does_not_satisfy_latest_paid_order_task():
    """Rejecting order 502 must not satisfy the latest-paid-order task when eligible order 503 exists."""
    refund_model = build_synthetic_refund_efsm()
    generator = CoverageGuidedGenerator(
        config=GenerateTestSuiteRequest(
            model_id=refund_model.model_id,
            version=refund_model.version,
            include_alternatives=True,
            include_negative_rejections=True,
        )
    )

    cases, _ = generator.generate(model=refund_model, suite_id="test_suite_gaps")

    # Find cases generated for the latest paid order task
    latest_paid_cases = [
        c
        for c in cases
        if "Refund my latest paid order" in c.task
        or c.category in (TestCategory.VALID, TestCategory.ALTERNATIVE)
    ]
    assert len(latest_paid_cases) > 0

    for case in latest_paid_cases:
        # All latest paid order cases must have expected outcome PASS, not REJECTION
        assert case.expected_outcome == ExpectedOutcomeType.PASS
        # Reference paths for latest paid order MUST terminate in REFUNDED (targeting order 503)
        for path in case.private_reference_paths:
            assert path[-1] == "REFUNDED"
            assert "REJECTED_UNPAID" not in path

    # The rejection case must have a distinct task prompt specifically targeting unpaid order 502
    negative_cases = [c for c in cases if c.category == TestCategory.NEGATIVE]
    assert len(negative_cases) > 0
    for neg_case in negative_cases:
        assert neg_case.expected_outcome == ExpectedOutcomeType.EXPECTED_REJECTION_PASS
        # Task must specify unpaid order 502, NOT generic latest paid order
        assert "502" in neg_case.task or "unpaid" in neg_case.task.lower()
        for path in neg_case.private_reference_paths:
            assert path[-1] == "REJECTED_UNPAID"


def test_regression_dedicated_unpaid_order_rejection_workflow():
    """Verify dedicated model for unpaid order 502 rejection exists and functions independently."""
    unpaid_efsm = build_synthetic_unpaid_order_rejection_efsm()
    assert unpaid_efsm.model_id == "unpaid_refund_rejection_efsm"
    assert "REJECTED_UNPAID" in unpaid_efsm.rejection_state_ids

    generator = CoverageGuidedGenerator(
        config=GenerateTestSuiteRequest(
            model_id=unpaid_efsm.model_id,
            version=unpaid_efsm.version,
            include_negative_rejections=True,
        )
    )
    cases, _ = generator.generate(model=unpaid_efsm, suite_id="test_suite_unpaid")
    assert len(cases) > 0
    assert any("502" in c.task for c in cases)


def test_regression_bounded_depth_limit_treated_as_unresolved_check_not_infeasibility():
    """Bounded validation limits must be treated as unresolved checks (warnings) rather than proof of infeasibility."""
    # Construct a model requiring search depth > max_search_depth (e.g. 5 steps with depth bound 3)
    states = [
        StateDefinition(id="S0", name="Start", type=StateType.INITIAL),
        StateDefinition(id="S1", name="Step 1", type=StateType.INTERMEDIATE),
        StateDefinition(id="S2", name="Step 2", type=StateType.INTERMEDIATE),
        StateDefinition(id="S3", name="Step 3", type=StateType.INTERMEDIATE),
        StateDefinition(id="S4", name="Done", type=StateType.TERMINAL_ACCEPTING),
    ]
    transitions = [
        TransitionDefinition(
            id="T01", source_state="S0", target_state="S1", trigger_event="e1"
        ),
        TransitionDefinition(
            id="T12", source_state="S1", target_state="S2", trigger_event="e2"
        ),
        TransitionDefinition(
            id="T23", source_state="S2", target_state="S3", trigger_event="e3"
        ),
        TransitionDefinition(
            id="T34", source_state="S3", target_state="S4", trigger_event="e4"
        ),
    ]
    deep_model = EFSMModelDefinition(
        project_id="proj_gaps",
        model_id="deep_chain",
        version="1.0.0",
        name="Deep Chain Model",
        states=states,
        initial_state_id="S0",
        accepting_state_ids=["S4"],
        transitions=transitions,
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="S4",
                description="Done",
            )
        ],
    )

    # Validate with max_search_depth = 2 (cannot reach S4 at depth 4)
    validator = BoundedSemanticValidator(max_search_depth=2)
    errors, warnings, diag = validator.validate(deep_model)

    # Must NOT record a critical error asserting infeasibility
    assert not any(e["check"] == "feasible_accepting_reachability" for e in errors)
    # Must record a warning regarding bounded search depth limit
    assert any(w["check"] == "bounded_search_depth_limit" for w in warnings)
    assert "unresolved_checks" in diag


def test_regression_exhausted_unreachable_state_is_critical_error():
    """A truly disconnected accepting state where reachable state space is exhausted remains a critical error."""
    states = [
        StateDefinition(id="S0", name="Start", type=StateType.INITIAL),
        StateDefinition(id="S1", name="Step 1", type=StateType.INTERMEDIATE),
        StateDefinition(
            id="S_UNREACHABLE",
            name="Unreachable Done",
            type=StateType.TERMINAL_ACCEPTING,
        ),
    ]
    transitions = [
        TransitionDefinition(
            id="T01", source_state="S0", target_state="S1", trigger_event="e1"
        ),
    ]
    disconnected_model = EFSMModelDefinition(
        project_id="proj_gaps",
        model_id="disconnected_model",
        version="1.0.0",
        name="Disconnected Model",
        states=states,
        initial_state_id="S0",
        accepting_state_ids=["S_UNREACHABLE"],
        transitions=transitions,
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="S_UNREACHABLE",
                description="Unreachable outcome",
            )
        ],
    )

    # Large depth limit so all reachable states (S0, S1) are explored without hitting limit
    validator = BoundedSemanticValidator(max_search_depth=10)
    errors, _warnings, _diag = validator.validate(disconnected_model)

    # Graph search exhausted without reaching depth limit -> true error
    assert any(e["check"] == "feasible_accepting_reachability" for e in errors)


def test_regression_approved_model_immutability(db_session: Session):
    """Preserve approved-model immutability and hash-linked validation."""
    efsm = build_synthetic_refund_efsm()
    repo = C2ModelRepository(db_session)
    val_service = ModelValidationService(db_session)

    repo.create_draft_model(efsm.project_id, efsm)
    val_service.validate_model_record(efsm.project_id, efsm.model_id, efsm.version)
    repo.approve_model(
        project_id=efsm.project_id,
        model_id=efsm.model_id,
        version=efsm.version,
        reviewer_id="reviewer_1",
        review_basis="Test basis",
    )

    # Direct draft creation with same version is rejected
    with pytest.raises(ModelAlreadyExistsError):
        repo.create_draft_model(efsm.project_id, efsm)
