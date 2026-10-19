"""Pure research metrics computation service for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    RecoveryVerdictCounts,
)
from app.components.c3_robustness_recovery.contracts.research import (
    AblationType,
    BaselineType,
    ConfusionMatrix,
    MetricScore,
    ResearchMetricsReport,
    ReviewerLabelRecord,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3MatchedPairModel,
)


def compute_metric_score(
    numerator: int,
    denominator: int,
    denominator_unit: str,
) -> MetricScore:
    """Compute a percentage score with safe zero-denominator handling and explicit unit accounting."""
    if denominator <= 0:
        return MetricScore(
            value=None,
            numerator=numerator,
            denominator=denominator,
            denominator_unit=denominator_unit,
            is_defined=False,
            undefined_reason=f"Denominator is zero ({denominator_unit}). Metric is undefined.",
        )
    return MetricScore(
        value=round(numerator / denominator, 4),
        numerator=numerator,
        denominator=denominator,
        denominator_unit=denominator_unit,
        is_defined=True,
        undefined_reason=None,
    )


def compute_research_metrics(
    experiment_id: str,
    target_domains: list[str],
    pair_models: list[C3MatchedPairModel | Any],
    evaluations: list[RecoveryEvaluationResult],
    labels: list[ReviewerLabelRecord] | None = None,
    total_case_families: int = 1,
    dev_families_count: int = 1,
    test_families_count: int = 0,
    planned_cases_count: int | None = None,
    blocked_cases_count: int = 0,
    unsupported_cases_count: int = 0,
    cancelled_cases_count: int = 0,
    error_cases_count: int = 0,
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3,
    ablation_type: AblationType = AblationType.NONE,
    demonstration_mode: bool = True,
    limitations: list[str] | None = None,
    evaluator_version: str = "1.2.0",
    rule_set_version: str = "1.2.0",
) -> ResearchMetricsReport:
    """Compute comprehensive research validation metrics with explicit denominators.

    Never invents perfect scores on empty or zero denominators.
    Strictly separates clean qualification from fault exposure and recovery verdicts.
    """
    labels_by_pair: dict[str, ReviewerLabelRecord] = {
        lbl.pair_id: lbl for lbl in (labels or [])
    }
    evals_by_pair: dict[str, RecoveryEvaluationResult] = {
        ev.pair_id: ev for ev in evaluations
    }

    executed_pairs = len(pair_models)
    planned_cases = (
        planned_cases_count if planned_cases_count is not None else executed_pairs
    )

    clean_counts = Counter(p.clean_qualification for p in pair_models)
    exposure_counts = Counter(p.exposure_status for p in pair_models)

    clean_qualified = clean_counts.get("QUALIFIED", 0)
    clean_disqualified = clean_counts.get("DISQUALIFIED", 0)
    clean_indeterminate = clean_counts.get("INDETERMINATE", 0)

    confirmed_exposure = exposure_counts.get("CONFIRMED", 0)
    not_triggered_exposure = exposure_counts.get("NOT_TRIGGERED", 0)
    unknown_exposure = exposure_counts.get("EXPOSURE_UNKNOWN", 0)

    # 1. Base Rates
    clean_qualification_rate = compute_metric_score(
        numerator=clean_qualified,
        denominator=executed_pairs,
        denominator_unit="executed_matched_pairs",
    )

    exposure_rate = compute_metric_score(
        numerator=confirmed_exposure,
        denominator=executed_pairs,
        denominator_unit="executed_matched_pairs",
    )

    # 2. Authoritative Recovery Verdicts
    verdict_counter: Counter[str] = Counter()
    for ev in evaluations:
        if ev.recovery_verdict:
            verdict_counter[ev.recovery_verdict.value] += 1

    evaluated_trials = len(evaluations)
    not_evaluated_count = max(0, executed_pairs - evaluated_trials)

    verdict_breakdown = RecoveryVerdictCounts(
        pass_completed_count=verdict_counter.get(
            RecoveryVerdict.PASS_COMPLETED.value, 0
        ),
        pass_graceful_count=verdict_counter.get(RecoveryVerdict.PASS_GRACEFUL.value, 0),
        fail_count=verdict_counter.get(RecoveryVerdict.FAIL.value, 0),
        inconclusive_count=verdict_counter.get(RecoveryVerdict.INCONCLUSIVE.value, 0),
        not_evaluated_count=not_evaluated_count,
    )

    # 3. Independent Ground Truth Labeling & Confusion Matrix
    cm: ConfusionMatrix | None = None
    accuracy_score: MetricScore | None = None
    precision_score: MetricScore | None = None
    recall_score: MetricScore | None = None
    f1_score: MetricScore | None = None
    false_pass_score: MetricScore | None = None
    abstention_score: MetricScore | None = None

    labeled_count = 0
    unlabeled_count = 0

    if labels:
        cm = ConfusionMatrix()
        for pair in pair_models:
            pair_id = pair.pair_id if hasattr(pair, "pair_id") else str(pair)
            lbl = labels_by_pair.get(pair_id)
            ev = evals_by_pair.get(pair_id)

            if not lbl:
                unlabeled_count += 1
                continue

            labeled_count += 1
            ref_has_defect = lbl.defect_present

            if not ev or ev.recovery_verdict is None:
                cm.unscored_count += 1
            elif ev.recovery_verdict == RecoveryVerdict.INCONCLUSIVE:
                cm.inconclusive_count += 1
            elif ev.recovery_verdict == RecoveryVerdict.FAIL:
                if ref_has_defect:
                    cm.true_positives += 1  # Correct defect detection
                else:
                    cm.false_positives += 1  # False alarm on healthy recovery
            elif ev.recovery_verdict in (
                RecoveryVerdict.PASS_COMPLETED,
                RecoveryVerdict.PASS_GRACEFUL,
            ):
                if ref_has_defect:
                    cm.false_negatives += 1  # False Pass! Missed defect
                else:
                    cm.true_negatives += 1  # Correctly verified pass

        # Scored decisions (excluding abstentions/inconclusive)
        total_decided = (
            cm.true_positives
            + cm.false_positives
            + cm.true_negatives
            + cm.false_negatives
        )

        accuracy_score = compute_metric_score(
            numerator=cm.true_positives + cm.true_negatives,
            denominator=total_decided,
            denominator_unit="decided_labeled_trials",
        )

        predicted_defects = cm.true_positives + cm.false_positives
        precision_score = compute_metric_score(
            numerator=cm.true_positives,
            denominator=predicted_defects,
            denominator_unit="predicted_defect_trials",
        )

        reference_defects = cm.true_positives + cm.false_negatives
        recall_score = compute_metric_score(
            numerator=cm.true_positives,
            denominator=reference_defects,
            denominator_unit="reference_defect_trials",
        )

        # F1 Score
        if (
            precision_score.is_defined
            and recall_score.is_defined
            and precision_score.value is not None
            and recall_score.value is not None
            and (precision_score.value + recall_score.value) > 0
        ):
            p = precision_score.value
            r = recall_score.value
            f1_val = round(2 * (p * r) / (p + r), 4)
            f1_score = MetricScore(
                value=f1_val,
                numerator=cm.true_positives * 2,
                denominator=predicted_defects + reference_defects,
                denominator_unit="sum_of_predicted_and_reference_defects",
                is_defined=True,
            )
        else:
            f1_score = MetricScore(
                value=None,
                denominator_unit="sum_of_predicted_and_reference_defects",
                is_defined=False,
                undefined_reason="Precision and/or Recall is 0 or undefined.",
            )

        # False-pass rate: False Negatives divided by reference defect trials
        false_pass_score = compute_metric_score(
            numerator=cm.false_negatives,
            denominator=reference_defects,
            denominator_unit="reference_defect_trials",
        )

        # Abstention rate: INCONCLUSIVE / all labeled trials evaluated
        total_eligible_labeled = total_decided + cm.inconclusive_count
        abstention_score = compute_metric_score(
            numerator=cm.inconclusive_count,
            denominator=total_eligible_labeled,
            denominator_unit="evaluated_labeled_trials",
        )

    all_limitations = list(limitations or [])
    if demonstration_mode:
        all_limitations.append(
            "Evaluation performed in DEMONSTRATION mode against in-memory double. "
            "Does not represent live target accuracy."
        )

    return ResearchMetricsReport(
        experiment_id=experiment_id,
        evaluator_version=evaluator_version,
        rule_set_version=rule_set_version,
        target_domains=target_domains,
        provenance_mode="DEMONSTRATION" if demonstration_mode else "LIVE",
        generated_at_utc=datetime.now(UTC).isoformat(),
        total_case_families=total_case_families,
        dev_families_count=dev_families_count,
        test_families_count=test_families_count,
        planned_cases_count=planned_cases,
        executed_pairs_count=executed_pairs,
        evaluated_trials_count=evaluated_trials,
        blocked_cases_count=blocked_cases_count,
        unsupported_cases_count=unsupported_cases_count,
        cancelled_cases_count=cancelled_cases_count,
        error_cases_count=error_cases_count,
        clean_qualified_count=clean_qualified,
        clean_disqualified_count=clean_disqualified,
        clean_indeterminate_count=clean_indeterminate,
        clean_qualification_rate=clean_qualification_rate,
        confirmed_exposure_count=confirmed_exposure,
        not_triggered_exposure_count=not_triggered_exposure,
        unknown_exposure_count=unknown_exposure,
        exposure_rate=exposure_rate,
        verdict_breakdown=verdict_breakdown,
        labeled_trials_count=labeled_count,
        unlabeled_trials_count=unlabeled_count,
        confusion_matrix=cm,
        accuracy=accuracy_score,
        precision=precision_score,
        recall=recall_score,
        f1_score=f1_score,
        false_pass_rate=false_pass_score,
        abstention_rate=abstention_score,
        baseline_type=baseline_type,
        ablation_type=ablation_type,
        demonstration_mode=demonstration_mode,
        limitations=all_limitations,
    )
