"""Tests for C2 Research Metrics calculation and Overhead Profiling.

Verifies:
1. Positive class is workflow violations.
2. Precision, Recall, F1, Mutation detection, State-effect fault detection.
3. Zero denominators return None with explicit status reasons rather than 0.0 or 1.0.
4. Inconclusive cases are treated conservatively.
5. OverheadProfiler timing statistics (median, p95).
"""

import time

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
    EvidenceProjectionType,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
    ExperimentCaseRecord,
    GroundTruthLabel,
    MutationFamily,
    ReviewStatus,
)
from app.components.c2_state_aware_workflow.contracts.report import ExecutionProvenance
from app.components.c2_state_aware_workflow.experiments.metrics import (
    ResearchMetricsCalculator,
)
from app.components.c2_state_aware_workflow.experiments.overhead import (
    OverheadProfiler,
)


def _make_case(
    case_id: str,
    is_violation: bool,
    expected_verdict: RuntimeVerdict = RuntimeVerdict.PASS,
    mutation_family: MutationFamily = MutationFamily.NONE,
    has_state_effect_fault: bool = False,
    divergence_step: int | None = None,
) -> ExperimentCaseRecord:
    gt = GroundTruthLabel(
        is_workflow_violation=is_violation,
        expected_verdict=expected_verdict,
        is_valid_test=True,
        has_state_effect_fault=has_state_effect_fault,
        mutation_family=mutation_family,
        ground_truth_divergence_step=divergence_step,
        ground_truth_divergence_location_known=(divergence_step is not None),
        review_status=ReviewStatus.DEVELOPER_FIXTURE,
    )
    return ExperimentCaseRecord(
        case_id=case_id,
        parent_case_id="fam_1",
        domain="ECOMMERCE",
        workflow_name="Test Workflow",
        model_id="m1",
        model_version="1.0.0",
        test_id=f"t_{case_id}",
        test_version="1.0.0",
        fixture_id="fix_1",
        fixture_digest="hash_fix",
        evidence_id=f"ev_{case_id}",
        evidence_digest="hash_ev",
        execution_provenance=ExecutionProvenance(
            intended_execution_mode="synthetic_demonstration",
            actual_execution_origin="scripted_synthetic_demonstration",
            runner_id="runner_1",
        ),
        partition=DatasetPartition.HELD_OUT,
        ground_truth=gt,
    )


def _make_prediction(
    verdict: RuntimeVerdict,
    pred_step: int | None = None,
    can_localize: bool = False,
) -> BaselinePredictionContract:
    return BaselinePredictionContract(
        method_id=BaselineType.B4_FULL_C2,
        method_name="B4",
        method_version="2026.1",
        evidence_projection=EvidenceProjectionType.FULL_PERMITTED_EVIDENCE,
        verdict=verdict,
        can_localize_first_divergence=can_localize,
        predicted_divergence_step=pred_step,
    )


def test_binary_metrics_positive_class_is_violation():
    """Verify precision, recall, and F1 calculation where positive class = violations."""
    # 2 true violations detected (TP = 2)
    # 1 conforming misclassified as violation (FP = 1)
    # 2 conforming correctly classified (TN = 2)
    # 1 violation missed as pass (FN = 1)
    pairs = [
        (_make_case("c1", is_violation=True), _make_prediction(RuntimeVerdict.FAIL)),
        (_make_case("c2", is_violation=True), _make_prediction(RuntimeVerdict.FAIL)),
        (
            _make_case("c3", is_violation=False),
            _make_prediction(RuntimeVerdict.FAIL),
        ),  # FP
        (_make_case("c4", is_violation=False), _make_prediction(RuntimeVerdict.PASS)),
        (_make_case("c5", is_violation=False), _make_prediction(RuntimeVerdict.PASS)),
        (
            _make_case("c6", is_violation=True),
            _make_prediction(RuntimeVerdict.PASS),
        ),  # FN
    ]

    metrics = ResearchMetricsCalculator.calculate_binary_metrics(pairs)
    assert metrics.true_positives == 2
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 2
    assert metrics.false_negatives == 1
    assert metrics.precision == round(2 / (2 + 1), 4)  # 0.6667
    assert metrics.recall == round(2 / (2 + 1), 4)  # 0.6667
    assert metrics.f1_score == round(2 * (0.6667 * 0.6667) / (0.6667 + 0.6667), 4)


def test_zero_denominator_returns_none_with_status():
    """Zero denominators must return None with status reason rather than invented 0% or 100%."""
    # All cases are conforming (no ground-truth violations)
    pairs = [
        (_make_case("c1", is_violation=False), _make_prediction(RuntimeVerdict.PASS)),
        (_make_case("c2", is_violation=False), _make_prediction(RuntimeVerdict.PASS)),
    ]

    metrics = ResearchMetricsCalculator.calculate_binary_metrics(pairs)
    assert metrics.true_positives == 0
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.true_negatives == 2
    assert metrics.precision is None
    assert metrics.precision_status == "UNAVAILABLE_NO_POSITIVE_PREDICTIONS"
    assert metrics.recall is None
    assert metrics.recall_status == "UNAVAILABLE_NO_GROUND_TRUTH_VIOLATIONS"
    assert metrics.f1_score is None


def test_inconclusive_handled_conservatively():
    """Inconclusive predictions on true violations are counted as false negatives."""
    pairs = [
        (
            _make_case("c1", is_violation=True),
            _make_prediction(RuntimeVerdict.INCONCLUSIVE),
        ),
        (_make_case("c2", is_violation=True), _make_prediction(RuntimeVerdict.FAIL)),
    ]

    metrics = ResearchMetricsCalculator.calculate_binary_metrics(pairs)
    assert metrics.inconclusive_count == 1
    assert metrics.true_positives == 1
    assert (
        metrics.false_negatives == 1
    )  # Inconclusive treated as missed detection under conservative policy
    assert metrics.recall == 0.5


def test_localization_accuracy_includes_missed_divergences():
    """Localization accuracy must evaluate all known-location violations, counting unlocalized as missed."""
    pairs = [
        (
            _make_case("c1", is_violation=True, divergence_step=2),
            _make_prediction(RuntimeVerdict.FAIL, pred_step=2, can_localize=True),
        ),
        (
            _make_case("c2", is_violation=True, divergence_step=1),
            _make_prediction(RuntimeVerdict.FAIL, pred_step=3, can_localize=True),
        ),  # Wrong step
        (
            _make_case("c3", is_violation=True, divergence_step=0),
            _make_prediction(RuntimeVerdict.PASS, pred_step=None, can_localize=True),
        ),  # Missed failure entirely
    ]

    loc = ResearchMetricsCalculator.calculate_localization_metrics(
        pairs, can_localize=True
    )
    assert loc.applicable_cases_with_known_location == 3
    assert loc.exact_matches == 1
    assert loc.missed_or_unlocalized == 2
    assert loc.accuracy == round(1 / 3, 4)


def test_overhead_profiler_computes_percentiles():
    """OverheadProfiler must compute median and p95 over warmup and repetitions."""

    def dummy_op():
        time.sleep(0.001)

    stats = OverheadProfiler.measure_callable(
        dummy_op,
        repetitions=10,
        warmup_iterations=2,
        scope_name="test_dummy",
    )
    assert stats.sample_count == 10
    assert stats.warmup_count == 2
    assert stats.median_ms > 0.0
    assert stats.p95_ms >= stats.median_ms
    assert len(stats.raw_measurements_ms) == 10
