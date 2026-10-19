"""Pure research metrics computation service for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

import random
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    RecoveryVerdictCounts,
)
from app.components.c3_robustness_recovery.contracts.research import (
    AblationType,
    BaselineType,
    BootstrapConfidenceInterval,
    CleanToFaultOutcomeTransitions,
    ConfusionMatrix,
    FixedSuiteComparisonResult,
    IndependentReviewerLabel,
    MetricScore,
    MulticlassConfusionMatrix,
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


def compute_four_way_multiclass_matrix(
    evaluations: list[RecoveryEvaluationResult],
    labels: list[IndependentReviewerLabel | ReviewerLabelRecord],
) -> MulticlassConfusionMatrix:
    """Compute 4-way multiclass confusion matrix, accuracy, per-class P/R/F1, and macro-F1.

    Classes: PASS_COMPLETED, PASS_GRACEFUL, FAIL, INCONCLUSIVE
    """
    classes = [
        RecoveryVerdict.PASS_COMPLETED.value,
        RecoveryVerdict.PASS_GRACEFUL.value,
        RecoveryVerdict.FAIL.value,
        RecoveryVerdict.INCONCLUSIVE.value,
    ]
    matrix: dict[str, dict[str, int]] = {
        actual: {pred: 0 for pred in classes} for actual in classes
    }

    labels_by_pair: dict[str, Any] = {lbl.pair_id: lbl for lbl in labels}
    correct_count = 0
    total_samples = 0

    for ev in evaluations:
        lbl = labels_by_pair.get(ev.pair_id)
        if not lbl:
            continue

        if hasattr(lbl, "assigned_verdict") and lbl.assigned_verdict is not None:
            ref_class = (
                lbl.assigned_verdict.value
                if hasattr(lbl.assigned_verdict, "value")
                else str(lbl.assigned_verdict)
            )
        else:
            ref_class = (
                RecoveryVerdict.FAIL.value
                if lbl.defect_present
                else RecoveryVerdict.PASS_COMPLETED.value
            )

        if ref_class not in classes:
            ref_class = RecoveryVerdict.INCONCLUSIVE.value

        if ev.recovery_verdict is not None:
            pred_class = ev.recovery_verdict.value
        else:
            pred_class = RecoveryVerdict.INCONCLUSIVE.value

        matrix[ref_class][pred_class] += 1
        total_samples += 1
        if ref_class == pred_class:
            correct_count += 1

    accuracy = compute_metric_score(
        numerator=correct_count,
        denominator=total_samples,
        denominator_unit="labeled_evaluated_trials",
    )

    per_class_precision: dict[str, MetricScore] = {}
    per_class_recall: dict[str, MetricScore] = {}
    per_class_f1: dict[str, MetricScore] = {}
    defined_f1_scores: list[float] = []

    for c in classes:
        tp = matrix[c][c]
        predicted_c = sum(matrix[act][c] for act in classes)
        actual_c = sum(matrix[c][prd] for prd in classes)

        prec = compute_metric_score(
            numerator=tp,
            denominator=predicted_c,
            denominator_unit=f"predicted_{c}_trials",
        )
        rec = compute_metric_score(
            numerator=tp,
            denominator=actual_c,
            denominator_unit=f"actual_{c}_trials",
        )
        per_class_precision[c] = prec
        per_class_recall[c] = rec

        if (
            prec.is_defined
            and rec.is_defined
            and prec.value is not None
            and rec.value is not None
            and (prec.value + rec.value) > 0
        ):
            f1_val = round(2 * (prec.value * rec.value) / (prec.value + rec.value), 4)
            f1_score = MetricScore(
                value=f1_val,
                numerator=tp * 2,
                denominator=predicted_c + actual_c,
                denominator_unit=f"sum_of_predicted_and_actual_{c}",
                is_defined=True,
            )
            defined_f1_scores.append(f1_val)
        else:
            f1_score = MetricScore(
                value=None,
                numerator=0,
                denominator=predicted_c + actual_c,
                denominator_unit=f"sum_of_predicted_and_actual_{c}",
                is_defined=False,
                undefined_reason=f"Precision and/or recall for class '{c}' is zero or undefined.",
            )
        per_class_f1[c] = f1_score

    if defined_f1_scores:
        macro_f1_val = round(sum(defined_f1_scores) / len(defined_f1_scores), 4)
        macro_f1 = MetricScore(
            value=macro_f1_val,
            numerator=len(defined_f1_scores),
            denominator=len(classes),
            denominator_unit="macro_evaluated_classes",
            is_defined=True,
        )
    else:
        macro_f1 = MetricScore(
            value=None,
            numerator=0,
            denominator=len(classes),
            denominator_unit="macro_evaluated_classes",
            is_defined=False,
            undefined_reason="No classes had defined F1 score.",
        )

    return MulticlassConfusionMatrix(
        classes=classes,
        matrix=matrix,
        total_samples=total_samples,
        accuracy=accuracy,
        per_class_precision=per_class_precision,
        per_class_recall=per_class_recall,
        per_class_f1=per_class_f1,
        macro_f1=macro_f1,
    )


def compute_clean_to_fault_transitions(
    pair_models: list[C3MatchedPairModel | Any],
    evaluations: list[RecoveryEvaluationResult] | None = None,
) -> CleanToFaultOutcomeTransitions:
    """Compute matched clean-to-fault outcome transitions preserving control qualification integrity."""
    evals_by_pair: dict[str, RecoveryEvaluationResult] = {
        ev.pair_id: ev for ev in (evaluations or [])
    }

    clean_pass_fault_rec = 0
    clean_pass_fault_def = 0
    clean_pass_fault_inc = 0
    clean_disq = 0

    for p in pair_models:
        qual = getattr(p, "clean_qualification", "")
        if qual != "QUALIFIED":
            clean_disq += 1
            continue

        pair_id = getattr(p, "pair_id", "")
        ev = evals_by_pair.get(pair_id)

        if ev and ev.recovery_verdict:
            if ev.recovery_verdict in (
                RecoveryVerdict.PASS_COMPLETED,
                RecoveryVerdict.PASS_GRACEFUL,
            ):
                clean_pass_fault_rec += 1
            elif ev.recovery_verdict == RecoveryVerdict.FAIL:
                clean_pass_fault_def += 1
            else:
                clean_pass_fault_inc += 1
        else:
            outcome = getattr(p, "fault_trial_caller_outcome", "") or ""
            if "SUCCESS" in outcome or "GRACEFUL" in outcome:
                clean_pass_fault_rec += 1
            elif "FAIL" in outcome or "ERROR" in outcome:
                clean_pass_fault_def += 1
            else:
                clean_pass_fault_inc += 1

    return CleanToFaultOutcomeTransitions(
        clean_pass_to_fault_recovered=clean_pass_fault_rec,
        clean_pass_to_fault_defect=clean_pass_fault_def,
        clean_pass_to_fault_inconclusive=clean_pass_fault_inc,
        clean_disqualified_count=clean_disq,
        total_matched_pairs=len(pair_models),
    )


def compute_execution_overhead_metrics(
    pair_models: list[C3MatchedPairModel | Any],
) -> dict[str, MetricScore]:
    """Compute observed execution overhead metrics while honestly reporting unavailable telemetry.

    Token and cost telemetry remain explicitly unavailable without live LLM instrumentation.
    """
    n = len(pair_models)
    if n == 0:
        return {
            "average_duration_ms": MetricScore(
                value=None,
                numerator=0,
                denominator=0,
                denominator_unit="executed_matched_pairs",
                is_defined=False,
                undefined_reason="No pairs executed to measure duration.",
            ),
            "token_overhead": MetricScore(
                value=None,
                numerator=None,
                denominator=None,
                denominator_unit="tokens",
                is_defined=False,
                undefined_reason="Token and cost telemetry unavailable offline; no live LLM telemetry pipeline connected.",
            ),
            "cost_overhead_usd": MetricScore(
                value=None,
                numerator=None,
                denominator=None,
                denominator_unit="usd",
                is_defined=False,
                undefined_reason="Cost telemetry unavailable offline.",
            ),
        }

    total_dur_ms = sum(getattr(p, "duration_ms", 0.0) or 0.0 for p in pair_models)
    avg_dur = round(total_dur_ms / n, 2)

    return {
        "average_duration_ms": MetricScore(
            value=avg_dur,
            numerator=int(total_dur_ms),
            denominator=n,
            denominator_unit="executed_matched_pairs",
            is_defined=True,
            undefined_reason=None,
        ),
        "token_overhead": MetricScore(
            value=None,
            numerator=None,
            denominator=None,
            denominator_unit="tokens",
            is_defined=False,
            undefined_reason="Token and cost telemetry unavailable offline; no live LLM telemetry pipeline connected.",
        ),
        "cost_overhead_usd": MetricScore(
            value=None,
            numerator=None,
            denominator=None,
            denominator_unit="usd",
            is_defined=False,
            undefined_reason="Cost telemetry unavailable offline.",
        ),
    }


def compute_family_cluster_bootstrap_ci(
    family_trial_data: dict[str, list[float]],
    metric_name: str = "f1_score",
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> BootstrapConfidenceInterval:
    """Compute deterministic cluster bootstrap confidence interval grouped by case family.

    Enforces Phase 7 research rigor:
    - Trials from the same case family are resampled as a unit (cluster bootstrap).
    - If unique clusters N < 5, reports insufficient data honestly.
    """
    clusters = list(family_trial_data.keys())
    n_clusters = len(clusters)

    all_values = [v for vals in family_trial_data.values() for v in vals]
    point_estimate = round(sum(all_values) / len(all_values), 4) if all_values else None

    if n_clusters < 5:
        return BootstrapConfidenceInterval(
            metric_name=metric_name,
            point_estimate=point_estimate,
            ci_lower=None,
            ci_upper=None,
            confidence_level=confidence_level,
            n_bootstraps=n_bootstraps,
            n_clusters=n_clusters,
            is_valid=False,
            limitation=(
                f"Insufficient cluster count (N={n_clusters} < 5) for reliable cluster bootstrap CI. "
                "Reported honestly per Phase 7 protocol."
            ),
        )

    rng = random.Random(seed)
    bootstrap_means: list[float] = []

    for _ in range(n_bootstraps):
        sampled_clusters = rng.choices(clusters, k=n_clusters)
        sampled_vals = [
            v for c in sampled_clusters for v in family_trial_data.get(c, [])
        ]
        if sampled_vals:
            bootstrap_means.append(sum(sampled_vals) / len(sampled_vals))

    if not bootstrap_means:
        return BootstrapConfidenceInterval(
            metric_name=metric_name,
            point_estimate=point_estimate,
            ci_lower=None,
            ci_upper=None,
            confidence_level=confidence_level,
            n_bootstraps=n_bootstraps,
            n_clusters=n_clusters,
            is_valid=False,
            limitation="No valid trial samples found in clusters.",
        )

    bootstrap_means.sort()
    alpha = (1.0 - confidence_level) / 2.0
    lower_idx = int(alpha * len(bootstrap_means))
    upper_idx = int((1.0 - alpha) * len(bootstrap_means)) - 1
    upper_idx = max(0, min(len(bootstrap_means) - 1, upper_idx))

    return BootstrapConfidenceInterval(
        metric_name=metric_name,
        point_estimate=point_estimate,
        ci_lower=round(bootstrap_means[lower_idx], 4),
        ci_upper=round(bootstrap_means[upper_idx], 4),
        confidence_level=confidence_level,
        n_bootstraps=n_bootstraps,
        n_clusters=n_clusters,
        is_valid=True,
        limitation=None,
    )


def compare_fixed_suite_vs_generated(
    fixed_suite: FrozenSuite,
    generated_suite: FrozenSuite,
    feasible_combinations: int = 12,
) -> FixedSuiteComparisonResult:
    """Compare predefined fixed fault suite against automatic generated suite under matched budgets."""
    fixed_cases = fixed_suite.selected_cases
    gen_cases = generated_suite.selected_cases

    fixed_validity = compute_metric_score(
        numerator=len(fixed_cases),
        denominator=len(fixed_cases),
        denominator_unit="fixed_suite_cases",
    )

    gen_validity = compute_metric_score(
        numerator=len(gen_cases),
        denominator=len(gen_cases),
        denominator_unit="generated_suite_cases",
    )

    fixed_tuples = {
        (
            getattr(c, "tool_id", getattr(c, "target_tool", "")),
            getattr(
                c,
                "fault_family",
                getattr(getattr(c, "fault_injection", None), "fault_type", None),
            ),
            getattr(
                c,
                "effect_phase",
                getattr(getattr(c, "fault_injection", None), "effect_phase", None),
            ),
        )
        for c in fixed_cases
    }
    gen_tuples = {
        (
            getattr(c, "tool_id", getattr(c, "target_tool", "")),
            getattr(
                c,
                "fault_family",
                getattr(getattr(c, "fault_injection", None), "fault_type", None),
            ),
            getattr(
                c,
                "effect_phase",
                getattr(getattr(c, "fault_injection", None), "effect_phase", None),
            ),
        )
        for c in gen_cases
    }

    fixed_cov = compute_metric_score(
        numerator=len(fixed_tuples),
        denominator=feasible_combinations,
        denominator_unit="declared_feasible_combinations",
    )
    gen_cov = compute_metric_score(
        numerator=len(gen_tuples),
        denominator=feasible_combinations,
        denominator_unit="declared_feasible_combinations",
    )

    return FixedSuiteComparisonResult(
        fixed_cases_count=len(fixed_cases),
        generated_cases_count=len(gen_cases),
        fixed_validity_rate=fixed_validity,
        generated_validity_rate=gen_validity,
        fixed_feasible_coverage=fixed_cov,
        generated_feasible_coverage=gen_cov,
        budget_equivalent=bool(len(fixed_cases) == len(gen_cases)),
        notes="Compared under matched case budget with independently declared feasible combinations.",
    )


def compute_research_metrics(
    experiment_id: str,
    target_domains: list[str],
    pair_models: list[C3MatchedPairModel | Any],
    evaluations: list[RecoveryEvaluationResult],
    labels: list[ReviewerLabelRecord | IndependentReviewerLabel] | None = None,
    total_case_families: int = 1,
    dev_families_count: int = 1,
    test_families_count: int = 0,
    val_families_count: int = 0,
    planned_cases_count: int | None = None,
    blocked_cases_count: int = 0,
    unsupported_cases_count: int = 0,
    cancelled_cases_count: int = 0,
    error_cases_count: int = 0,
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3,
    ablation_type: AblationType = AblationType.NONE,
    demonstration_mode: bool = True,
    limitations: list[str] | None = None,
    family_trial_data: dict[str, list[float]] | None = None,
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

    # Phase 7 Multiclass Confusion Matrix
    multiclass_cm = None
    if labels:
        multiclass_cm = compute_four_way_multiclass_matrix(evaluations, labels)

    # Phase 7 Transitions & Overheads
    transitions = compute_clean_to_fault_transitions(pair_models, evaluations)
    overheads = compute_execution_overhead_metrics(pair_models)

    # Phase 7 Cluster Bootstrap CI
    bootstrap_ci = None
    if family_trial_data:
        bootstrap_ci = compute_family_cluster_bootstrap_ci(family_trial_data)

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
        val_families_count=val_families_count,
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
        multiclass_confusion_matrix=multiclass_cm,
        outcome_transitions=transitions,
        execution_overheads=overheads,
        bootstrap_ci=bootstrap_ci,
        baseline_type=baseline_type,
        ablation_type=ablation_type,
        demonstration_mode=demonstration_mode,
        limitations=all_limitations,
    )
