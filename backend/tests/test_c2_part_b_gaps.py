"""Regression tests for Day 3 Part B reporting and reproduction gap fixes.

Verifies:
1. Expected-rejection path coverage: Completed declared rejection paths count as completed selected paths.
2. Fault-detection accuracy: Remains None (unavailable) on normal runs without labelled faulty datasets.
3. Composite coverage: Marked with documented formula and explicit status.
4. Actual reproduction: Independent replay verification re-runs the evaluator and verifies semantic equality.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GenerateTestSuiteRequest,
)
from app.components.c2_state_aware_workflow.evaluator.coverage import (
    ObservedCoverageEngine,
)
from app.components.c2_state_aware_workflow.evaluator.service import (
    WorkflowEvaluationService,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.generator.service import (
    TestGenerationService,
)
from app.components.c2_state_aware_workflow.integrations.service import (
    C2IntegrationService,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def refund_model():
    return build_synthetic_refund_efsm()


def test_expected_rejection_path_counted_in_selected_path_coverage(refund_model):
    """Completed declared rejection paths must count as completed selected paths without requiring positive acceptance."""
    engine = ObservedCoverageEngine(refund_model)
    catalogue = engine.build_selected_path_catalogue()
    assert "path_rejection_unpaid" in catalogue

    rejection_seq = catalogue["path_rejection_unpaid"]

    # Rejection run completed: reached rejection state without premature failure
    cov = engine.compute_coverage(
        covered_transitions=set(rejection_seq),
        guard_true_outcomes={"T_RETRIEVE_ORDERS", "T_REJECT_UNPAID_ORDER"},
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects={"T_REJECT_UNPAID_ORDER_effect_0"},
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=rejection_seq,
        is_terminal_accepting=False,
        is_terminal_rejection=True,
    )

    path_cov = cov.selected_path_coverage
    assert "path_rejection_unpaid" in path_cov.completed_paths
    assert "path_rejection_unpaid" in path_cov.covered_targets
    assert path_cov.numerator == 1


def test_fault_detection_accuracy_unavailable_without_labelled_dataset(refund_model):
    """Fault detection accuracy must return None with explicit status reason on normal execution evidence."""
    engine = ObservedCoverageEngine(refund_model)
    cov = engine.compute_coverage(
        covered_transitions={"T_RETRIEVE_ORDERS", "T_SELECT_LATEST_PAID_ORDER"},
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )

    eff_cov = cov.state_effect_coverage
    # Must NOT be hardcoded to 1.0 or 0.0
    assert eff_cov.fault_detection_accuracy is None
    assert "UNAVAILABLE" in eff_cov.fault_detection_status


def test_composite_coverage_has_documented_formula(refund_model):
    """DetailedObservedCoverage composite metric must have an explicitly documented formula and status."""
    engine = ObservedCoverageEngine(refund_model)
    cov = engine.compute_coverage(
        covered_transitions={"T_RETRIEVE_ORDERS"},
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )

    assert cov.composite_coverage_status == "COMPOSITE_INFORMATIONAL_ONLY"
    assert cov.composite_coverage_formula is not None
    assert "unweighted_arithmetic_mean" in cov.composite_coverage_formula


def test_actual_reproduction_verification(db_session: Session, refund_model):
    """Independent replay must actually rerun the evaluator against stored evidence and verify semantic equality."""
    project_id = "proj_replay_test"
    repo = C2ModelRepository(db_session)
    val_service = ModelValidationService(db_session)
    gen_service = TestGenerationService(db_session)
    orch_service = C2IntegrationService(db_session)
    eval_service = WorkflowEvaluationService(db_session)

    # Setup approved model and suite
    model = refund_model.model_copy(update={"project_id": project_id})
    repo.create_draft_model(project_id, model)
    val_service.validate_model_record(project_id, model.model_id, model.version)
    repo.approve_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        reviewer_id="reviewer_replay",
        review_basis="Approved for replay test",
    )

    suite = gen_service.generate_suite_for_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        request=GenerateTestSuiteRequest(
            model_id=model.model_id,
            version=model.version,
            include_mutations=False,
            case_budget=2,
        ),
    )

    cases = repo.list_test_cases(project_id, suite.suite_id)
    case = cases[0]

    # Run case and persist evaluation
    run_res = orch_service.run_case(
        project_id=project_id,
        suite_id=suite.suite_id,
        test_id=case.test_id,
        run_id="run_replay_001",
    )
    assert run_res.evaluation_id is not None

    # Independently verify reproduction
    replay_res = eval_service.verify_execution_reproduction(
        project_id=project_id,
        evaluation_id=run_res.evaluation_id,
    )

    assert replay_res.evaluated_freshly is True
    assert replay_res.semantic_equality is True
    assert replay_res.is_reproducible is True
    assert replay_res.replay_verdict == run_res.verdict
    assert len(replay_res.differences) == 0
