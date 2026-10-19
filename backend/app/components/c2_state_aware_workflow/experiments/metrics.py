"""Research metrics calculation for C2 baseline comparisons.

Treats workflow violations as the positive class.
Handles zero denominators explicitly without inventing scores.
Keeps decided-case and conservative evaluation transparent.
"""

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.experiment import (
    BinaryClassificationMetrics,
    DatasetPartition,
    DivergenceLocalizationMetrics,
    ExperimentCaseRecord,
    MethodResearchMetrics,
    MutationFamily,
)

VIOLATION_VERDICTS = {
    RuntimeVerdict.FAIL,
}

CONFORMING_VERDICTS = {
    RuntimeVerdict.PASS,
    RuntimeVerdict.EXPECTED_REJECTION_PASS,
}

INCONCLUSIVE_VERDICTS = {
    RuntimeVerdict.INCONCLUSIVE,
    RuntimeVerdict.MODEL_NOT_READY,
    RuntimeVerdict.TEST_NOT_READY,
}


class ResearchMetricsCalculator:
    """Calculates scientifically rigorous evaluation metrics over frozen experiment cases."""

    @staticmethod
    def calculate_binary_metrics(
        case_pairs: list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
    ) -> BinaryClassificationMetrics:
        """Calculate binary detection metrics where workflow violations are the positive class."""
        tp = 0
        fp = 0
        tn = 0
        fn = 0
        inconclusive_count = 0
        excluded_count = 0

        # Mutation tracking
        mutations_present = 0
        mutations_detected = 0

        # State effect fault tracking
        state_faults_present = 0
        state_faults_detected = 0

        for case, pred in case_pairs:
            gt = case.ground_truth
            is_gt_violation = gt.is_workflow_violation
            pred_verdict = pred.verdict

            if pred_verdict in INCONCLUSIVE_VERDICTS:
                inconclusive_count += 1
                if is_gt_violation:
                    fn += 1  # Conservative policy: inconclusive on true violation is treated as missed detection
                continue

            is_pred_violation = pred_verdict in VIOLATION_VERDICTS
            is_pred_conforming = pred_verdict in CONFORMING_VERDICTS

            if not is_pred_violation and not is_pred_conforming:
                excluded_count += 1
                continue

            if is_gt_violation and is_pred_violation:
                tp += 1
            elif not is_gt_violation and is_pred_violation:
                fp += 1
            elif not is_gt_violation and is_pred_conforming:
                tn += 1
            elif is_gt_violation and is_pred_conforming:
                fn += 1

            # Check mutation detection
            if gt.mutation_family != MutationFamily.NONE:
                mutations_present += 1
                if is_pred_violation:
                    mutations_detected += 1

            # Check state-effect fault detection
            if gt.has_state_effect_fault:
                state_faults_present += 1
                if is_pred_violation:
                    state_faults_detected += 1

        total_evaluated = len(case_pairs)

        # Precision
        if (tp + fp) > 0:
            precision = round(tp / (tp + fp), 4)
            precision_status = "CALCULATED"
        else:
            precision = None
            precision_status = "UNAVAILABLE_NO_POSITIVE_PREDICTIONS"

        # Recall
        if (tp + fn) > 0:
            recall = round(tp / (tp + fn), 4)
            recall_status = "CALCULATED"
        else:
            recall = None
            recall_status = "UNAVAILABLE_NO_GROUND_TRUTH_VIOLATIONS"

        # F1
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = round(2 * (precision * recall) / (precision + recall), 4)
            f1_status = "CALCULATED"
        else:
            f1 = None
            f1_status = "UNAVAILABLE_CANNOT_COMPUTE_F1"

        # Mutation Detection
        if mutations_present > 0:
            mutation_score = round(mutations_detected / mutations_present, 4)
            mutation_status = "CALCULATED"
        else:
            mutation_score = None
            mutation_status = "UNAVAILABLE_NO_LABELLED_MUTATIONS"

        # State-Effect Fault Detection
        if state_faults_present > 0:
            state_fault_score = round(state_faults_detected / state_faults_present, 4)
            state_fault_status = "CALCULATED"
        else:
            state_fault_score = None
            state_fault_status = "UNAVAILABLE_NO_LABELLED_STATE_EFFECT_FAULTS"

        # Inconclusive Rate
        if total_evaluated > 0:
            inconclusive_rate = round(inconclusive_count / total_evaluated, 4)
            inconclusive_status = "CALCULATED"
        else:
            inconclusive_rate = None
            inconclusive_status = "UNAVAILABLE_NO_EVALUATED_CASES"

        return BinaryClassificationMetrics(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            inconclusive_count=inconclusive_count,
            excluded_count=excluded_count,
            total_evaluated=total_evaluated,
            precision=precision,
            precision_status=precision_status,
            recall=recall,
            recall_status=recall_status,
            f1_score=f1,
            f1_status=f1_status,
            mutation_detection_score=mutation_score,
            mutation_detection_status=mutation_status,
            state_effect_fault_detection_score=state_fault_score,
            state_effect_fault_detection_status=state_fault_status,
            inconclusive_rate=inconclusive_rate,
            inconclusive_rate_status=inconclusive_status,
        )

    @staticmethod
    def calculate_localization_metrics(
        case_pairs: list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
        can_localize: bool,
    ) -> DivergenceLocalizationMetrics:
        """Calculate first-divergence localization accuracy over violations with known location."""
        if not can_localize:
            return DivergenceLocalizationMetrics(
                can_localize=False,
                applicable_cases_with_known_location=0,
                exact_matches=0,
                missed_or_unlocalized=0,
                accuracy=None,
                accuracy_status="UNAVAILABLE_METHOD_CANNOT_LOCALIZE_EARLIEST_DIVERGENCE",
                cases_with_unknown_location_excluded=0,
            )

        applicable_count = 0
        exact_matches = 0
        missed_or_unlocalized = 0
        unknown_location_excluded = 0

        for case, pred in case_pairs:
            gt = case.ground_truth
            if not gt.is_workflow_violation:
                continue  # Only violations have divergence

            if not gt.ground_truth_divergence_location_known:
                unknown_location_excluded += 1
                continue

            applicable_count += 1
            pred_step = pred.predicted_divergence_step
            gt_step = gt.ground_truth_divergence_step

            # Match criteria: exact step index match
            if pred_step is not None and gt_step is not None and pred_step == gt_step:
                exact_matches += 1
            else:
                missed_or_unlocalized += 1

        if applicable_count > 0:
            accuracy = round(exact_matches / applicable_count, 4)
            accuracy_status = "CALCULATED"
        else:
            accuracy = None
            accuracy_status = "UNAVAILABLE_NO_CASES_WITH_KNOWN_DIVERGENCE_LOCATION"

        return DivergenceLocalizationMetrics(
            can_localize=True,
            applicable_cases_with_known_location=applicable_count,
            exact_matches=exact_matches,
            missed_or_unlocalized=missed_or_unlocalized,
            accuracy=accuracy,
            accuracy_status=accuracy_status,
            cases_with_unknown_location_excluded=unknown_location_excluded,
        )

    @classmethod
    def calculate_method_metrics(
        cls,
        method_id: BaselineType,
        method_name: str,
        partition: DatasetPartition,
        case_pairs: list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
        overhead_median_ms: float = 0.0,
        overhead_p95_ms: float = 0.0,
        coverage_metrics: dict[str, float | None] | None = None,
    ) -> MethodResearchMetrics:
        """Compute full research metrics block for a baseline on a dataset partition."""
        cov = coverage_metrics or {}
        sample_count = len(case_pairs)
        can_localize = (
            any(p.can_localize_first_divergence for _, p in case_pairs)
            if case_pairs
            else False
        )

        binary_metrics = cls.calculate_binary_metrics(case_pairs)
        loc_metrics = cls.calculate_localization_metrics(
            case_pairs, can_localize=can_localize
        )

        return MethodResearchMetrics(
            method_id=method_id,
            method_name=method_name,
            partition=partition,
            sample_count=sample_count,
            detection_metrics=binary_metrics,
            localization_metrics=loc_metrics,
            overhead_median_ms=overhead_median_ms,
            overhead_p95_ms=overhead_p95_ms,
            transition_coverage=cov.get("transition_coverage"),
            guard_outcome_coverage=cov.get("guard_outcome_coverage"),
            selected_path_coverage=cov.get("selected_path_coverage"),
            state_effect_coverage=cov.get("state_effect_coverage"),
        )
