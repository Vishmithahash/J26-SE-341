"""Tests for C2 Observed Workflow Coverage Engine.

Verifies:
1. Transition coverage: unique transition IDs / defined targets, exact numerators/denominators.
2. Guard-outcome coverage: TRUE and FALSE outcomes tracked separately (denominator = guards * 2),
   UNKNOWN observations preserved but not counted as covered, repeated observations deduplicated.
3. Selected-path coverage: explicit catalogue of normal, alternative, and rejection paths;
   partial paths rejected, completed paths required.
4. State-effect coverage: satisfied, violated, and unknown effect checks tracked;
   effect-check ratio kept separate from fault-detection accuracy.
5. Suite aggregation: unique target unions, no inflation on repeated runs, incompatible model version isolation.
"""

import pytest

from app.components.c2_state_aware_workflow.evaluator.coverage import (
    ObservedCoverageEngine,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)


@pytest.fixture
def refund_model():
    return build_synthetic_refund_efsm()


def test_transition_coverage_exact_numerators_and_denominators(refund_model):
    engine = ObservedCoverageEngine(refund_model)
    all_transitions = {t.id for t in refund_model.transitions}
    total_transitions = len(all_transitions)

    # Empty run
    cov = engine.compute_coverage(
        covered_transitions=set(),
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )
    assert cov.transition_coverage.numerator == 0
    assert cov.transition_coverage.denominator == total_transitions
    assert cov.transition_coverage.coverage_ratio == 0.0
    assert len(cov.transition_coverage.uncovered_targets) == total_transitions

    # Partial run with 2 transitions
    cov2 = engine.compute_coverage(
        covered_transitions={"T_RETRIEVE_ORDERS", "T_SELECT_LATEST_PAID_ORDER"},
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )
    assert cov2.transition_coverage.numerator == 2
    assert cov2.transition_coverage.denominator == total_transitions
    assert cov2.transition_coverage.covered_targets == [
        "T_RETRIEVE_ORDERS",
        "T_SELECT_LATEST_PAID_ORDER",
    ]
    assert "T_DIRECT_REQUEST_REFUND" in cov2.transition_coverage.uncovered_targets

    # Extraneous transition ID not in model is ignored
    cov3 = engine.compute_coverage(
        covered_transitions={"T_RETRIEVE_ORDERS", "NON_EXISTENT_TRANSITION"},
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )
    assert cov3.transition_coverage.numerator == 1
    assert cov3.transition_coverage.covered_targets == ["T_RETRIEVE_ORDERS"]


def test_guard_outcome_coverage_separates_true_and_false(refund_model):
    engine = ObservedCoverageEngine(refund_model)
    guarded_transitions = [t for t in refund_model.transitions if t.guard]
    expected_total_guards = len(guarded_transitions)
    expected_outcome_targets = expected_total_guards * 2

    # Simulate T_SELECT_LATEST_PAID_ORDER guard evaluating to TRUE, T_DIRECT_REQUEST_REFUND evaluating to FALSE
    cov = engine.compute_coverage(
        covered_transitions={"T_RETRIEVE_ORDERS", "T_SELECT_LATEST_PAID_ORDER"},
        guard_true_outcomes={"T_SELECT_LATEST_PAID_ORDER"},
        guard_false_outcomes={"T_DIRECT_REQUEST_REFUND"},
        guard_unknown_observations={"T_REJECT_UNPAID_ORDER"},
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )

    guard_cov = cov.guard_outcome_coverage
    assert guard_cov.denominator == expected_outcome_targets
    assert guard_cov.total_guards_defined == expected_total_guards
    assert guard_cov.numerator == 2  # 1 TRUE + 1 FALSE
    assert "T_SELECT_LATEST_PAID_ORDER_outcome_TRUE" in guard_cov.covered_targets
    assert "T_DIRECT_REQUEST_REFUND_outcome_FALSE" in guard_cov.covered_targets
    assert "T_SELECT_LATEST_PAID_ORDER_outcome_FALSE" in guard_cov.uncovered_targets

    # UNKNOWN is preserved but NOT counted as covered
    assert "T_REJECT_UNPAID_ORDER" in guard_cov.unknown_or_ambiguous_observations
    assert "T_REJECT_UNPAID_ORDER_outcome_TRUE" not in guard_cov.covered_targets
    assert "T_REJECT_UNPAID_ORDER_outcome_FALSE" not in guard_cov.covered_targets
    assert guard_cov.guards_unknown_count == 1
    assert guard_cov.repeated_observations_deduplicated is True


def test_selected_path_coverage_full_vs_partial(refund_model):
    engine = ObservedCoverageEngine(refund_model)
    catalogue = engine.build_selected_path_catalogue()
    assert "path_normal_refund" in catalogue
    assert "path_alternative_inspection" in catalogue
    assert "path_rejection_unpaid" in catalogue

    normal_seq = catalogue["path_normal_refund"]

    # 1. Partial path: only executed first 2 transitions of normal path
    cov_partial = engine.compute_coverage(
        covered_transitions=set(normal_seq[:2]),
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=normal_seq[:2],
        is_terminal_accepting=False,
    )
    assert cov_partial.selected_path_coverage.numerator == 0
    assert (
        "path_normal_refund" not in cov_partial.selected_path_coverage.covered_targets
    )
    assert "path_normal_refund" in cov_partial.selected_path_coverage.uncovered_targets

    # 2. Complete path but not terminal accepting (e.g. divergence before final verification)
    cov_non_accepting = engine.compute_coverage(
        covered_transitions=set(normal_seq),
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=normal_seq,
        is_terminal_accepting=False,
    )
    assert cov_non_accepting.selected_path_coverage.numerator == 0

    # 3. Fully completed normal path with terminal accepting verdict
    cov_complete = engine.compute_coverage(
        covered_transitions=set(normal_seq),
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=normal_seq,
        is_terminal_accepting=True,
    )
    assert cov_complete.selected_path_coverage.numerator == 1
    assert "path_normal_refund" in cov_complete.selected_path_coverage.covered_targets
    assert (
        "path_alternative_inspection"
        in cov_complete.selected_path_coverage.uncovered_targets
    )


def test_state_effect_coverage_satisfaction_violation_unknown(refund_model):
    engine = ObservedCoverageEngine(refund_model)

    cov = engine.compute_coverage(
        covered_transitions={
            "T_RETRIEVE_ORDERS",
            "T_SELECT_LATEST_PAID_ORDER",
            "T_VERIFY_REFUND",
        },
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects={"T_VERIFY_REFUND_effect_0"},
        violated_effects={"T_REJECT_UNPAID_ORDER_effect_0"},
        unknown_effects={"T_NONEXISTENT_effect_0"},
    )

    eff_cov = cov.state_effect_coverage
    # Checked effects include both satisfied and violated checks for valid effect targets
    assert "T_VERIFY_REFUND_effect_0" in eff_cov.satisfied_checks
    assert "T_REJECT_UNPAID_ORDER_effect_0" in eff_cov.violated_checks

    assert "T_VERIFY_REFUND_effect_0" in eff_cov.covered_targets
    assert "T_REJECT_UNPAID_ORDER_effect_0" in eff_cov.covered_targets
    assert eff_cov.numerator == 2
    assert eff_cov.denominator == 2
    assert eff_cov.coverage_ratio == 1.0
    # Fault detection accuracy requires labelled evaluations and is not computed from normal effect checks
    assert eff_cov.fault_detection_accuracy is None
    assert (
        eff_cov.fault_detection_status
        == "UNAVAILABLE_REQUIRES_LABELLED_FAULTY_EVALUATIONS"
    )


def test_suite_aggregation_deduplication_and_model_isolation(refund_model):
    engine = ObservedCoverageEngine(refund_model)
    catalogue = engine.build_selected_path_catalogue()
    normal_seq = catalogue["path_normal_refund"]
    alt_seq = catalogue["path_alternative_inspection"]

    # Run 1: Happy path
    run1 = engine.compute_coverage(
        covered_transitions=set(normal_seq),
        guard_true_outcomes={"T_SELECT_LATEST_PAID_ORDER", "T_DIRECT_REQUEST_REFUND"},
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects={"T_VERIFY_REFUND_effect_0"},
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=normal_seq,
        is_terminal_accepting=True,
    )

    # Run 2: Exact duplicate of Run 1
    run2 = engine.compute_coverage(
        covered_transitions=set(normal_seq),
        guard_true_outcomes={"T_SELECT_LATEST_PAID_ORDER", "T_DIRECT_REQUEST_REFUND"},
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects={"T_VERIFY_REFUND_effect_0"},
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=normal_seq,
        is_terminal_accepting=True,
    )

    # Aggregate 5 repeated identical runs: must NOT inflate counts
    agg_repeated = ObservedCoverageEngine.aggregate_suite_coverage(
        model=refund_model,
        run_coverages=[run1, run2, run1, run2, run1],
    )
    assert (
        agg_repeated.transition_coverage.numerator == run1.transition_coverage.numerator
    )
    assert (
        agg_repeated.guard_outcome_coverage.numerator
        == run1.guard_outcome_coverage.numerator
    )
    assert agg_repeated.selected_path_coverage.numerator == 1
    assert (
        agg_repeated.state_effect_coverage.numerator
        == run1.state_effect_coverage.numerator
    )

    # Run 3: Alternative inspection path
    run3 = engine.compute_coverage(
        covered_transitions=set(alt_seq),
        guard_true_outcomes={
            "T_SELECT_LATEST_PAID_ORDER",
            "T_INSPECTED_REQUEST_REFUND",
        },
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects={"T_VERIFY_REFUND_effect_0"},
        violated_effects=set(),
        unknown_effects=set(),
        completed_path_history=alt_seq,
        is_terminal_accepting=True,
    )

    # Aggregate Run 1 + Run 3: union of unique targets
    agg_combined = ObservedCoverageEngine.aggregate_suite_coverage(
        model=refund_model,
        run_coverages=[run1, run3],
    )
    expected_trans = set(normal_seq) | set(alt_seq)
    assert set(agg_combined.transition_coverage.covered_targets) == expected_trans
    assert agg_combined.selected_path_coverage.numerator == 2
    assert "path_normal_refund" in agg_combined.selected_path_coverage.covered_targets
    assert (
        "path_alternative_inspection"
        in agg_combined.selected_path_coverage.covered_targets
    )

    # Incompatible model isolation: run with different model_id or version is skipped
    run_incompatible = run3.model_copy(update={"model_version": "9.9.9"})
    agg_isolated = ObservedCoverageEngine.aggregate_suite_coverage(
        model=refund_model,
        run_coverages=[run1, run_incompatible],
    )
    assert agg_isolated.selected_path_coverage.numerator == 1
    assert (
        "path_alternative_inspection"
        not in agg_isolated.selected_path_coverage.covered_targets
    )
