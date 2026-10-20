"""Experiment runner for C2 baseline comparisons (B1-B4).

Executes all baselines over the exact same retained execution evidence.
Enforces partition isolation and non-leakage.
Produces standardized ExperimentComparisonReport and C2ExperimentCaseResult records.
"""

import math
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
)
from app.components.c2_state_aware_workflow.baselines.service import (
    BaselineEvaluationService,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
    ExperimentCaseRecord,
    ExperimentComparisonReport,
    ExperimentDatasetManifest,
    MethodResearchMetrics,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.experiments.metrics import (
    ResearchMetricsCalculator,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2ExperimentCaseResult,
)


class ExperimentRunner:
    """Runs versioned comparative experiments across B1, B2, B3, and B4."""

    def __init__(self, baseline_service: BaselineEvaluationService | None = None):
        self.baseline_service = baseline_service or BaselineEvaluationService()

    def run_experiment(
        self,
        experiment_id: str,
        experiment_name: str,
        manifest: ExperimentDatasetManifest,
        models_by_id: dict[str, EFSMModelDefinition],
        tests_by_id: dict[str, GeneratedTestDefinition],
        eval_methods: list[BaselineType] | None = None,
        target_partition: DatasetPartition | None = None,
    ) -> tuple[ExperimentComparisonReport, list[C2ExperimentCaseResult]]:
        """Execute baseline comparison experiment over frozen dataset manifest."""
        methods_to_run = eval_methods or [
            BaselineType.B1_FINAL_STATE_ONLY,
            BaselineType.B2_TRACE_ONLY,
            BaselineType.B3_MILESTONE_BASED,
            BaselineType.B4_FULL_C2,
        ]

        # Filter cases if partition specified
        cases_to_evaluate = [
            c
            for c in manifest.cases
            if target_partition is None or c.partition == target_partition
        ]

        # Results index: method_id -> list of (case, prediction)
        method_predictions: dict[
            BaselineType,
            list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
        ] = {m: [] for m in methods_to_run}

        db_case_results: list[C2ExperimentCaseResult] = []

        for case in cases_to_evaluate:
            model = models_by_id.get(case.model_id)
            test_def = tests_by_id.get(case.test_id)
            evidence = case.frozen_evidence
            fixture = case.frozen_fixture or {}

            if not model or not test_def or not evidence:
                # Mark as excluded if required assets missing
                for m in methods_to_run:
                    db_case_results.append(
                        C2ExperimentCaseResult(
                            project_id=manifest.project_id,
                            experiment_id=experiment_id,
                            case_id=case.case_id,
                            method_id=m.value,
                            partition=case.partition.value,
                            verdict=RuntimeVerdict.TEST_NOT_READY.value,
                            is_violation=False,
                            can_localize=False,
                            evaluator_timing_ms=0.0,
                            source_evidence_digest="",
                            evidence_digest_consumed="",
                            is_excluded=True,
                            exclusion_reason="MISSING_FROZEN_ASSETS",
                            result_payload={
                                "error": "Missing frozen model, test, or evidence."
                            },
                        )
                    )
                continue

            for m in methods_to_run:
                t0 = time.perf_counter_ns()
                pred = self.baseline_service.evaluate_baseline(
                    baseline_type=m,
                    model=model,
                    test_def=test_def,
                    evidence=evidence,
                    fixture_data=fixture,
                )
                t1 = time.perf_counter_ns()
                elapsed_ms = round((t1 - t0) / 1_000_000.0, 3)

                # Use actual timing
                pred_with_timing = pred.model_copy(
                    update={"evaluator_timing_ms": elapsed_ms}
                )

                method_predictions[m].append((case, pred_with_timing))

                is_viol = pred_with_timing.verdict == RuntimeVerdict.FAIL

                db_case_results.append(
                    C2ExperimentCaseResult(
                        project_id=manifest.project_id,
                        experiment_id=experiment_id,
                        case_id=case.case_id,
                        method_id=m.value,
                        partition=case.partition.value,
                        verdict=pred_with_timing.verdict.value,
                        is_violation=is_viol,
                        can_localize=pred_with_timing.can_localize_first_divergence,
                        first_divergence_predicted_step=pred_with_timing.predicted_divergence_step,
                        first_divergence_event_id=pred_with_timing.predicted_divergence_event_id,
                        evaluator_timing_ms=elapsed_ms,
                        source_evidence_digest=pred_with_timing.source_evidence_digest,
                        evidence_digest_consumed=pred_with_timing.evidence_digest_consumed,
                        is_excluded=False,
                        result_payload=pred_with_timing.model_dump(mode="json"),
                    )
                )

        # Compute test validity rate
        total_cases = len(cases_to_evaluate)
        valid_cases = sum(1 for c in cases_to_evaluate if c.ground_truth.is_valid_test)
        validity_rate = round(valid_cases / total_cases, 4) if total_cases > 0 else None
        validity_status = "CALCULATED" if total_cases > 0 else "UNAVAILABLE_NO_CASES"

        # Compute test validity rate
        total_cases = len(cases_to_evaluate)
        valid_cases = sum(1 for c in cases_to_evaluate if c.ground_truth.is_valid_test)
        validity_rate = round(valid_cases / total_cases, 4) if total_cases > 0 else None
        validity_status = "CALCULATED" if total_cases > 0 else "UNAVAILABLE_NO_CASES"

        # Compute method metrics partitioned by DEVELOPMENT, HELD_OUT, and ALL_CASES
        metrics_by_partition: dict[str, dict[str, MethodResearchMetrics]] = {}

        # 1. DEVELOPMENT
        dev_metrics = self._compute_partition_metrics(
            methods_to_run=methods_to_run,
            method_predictions=method_predictions,
            partition=DatasetPartition.DEVELOPMENT,
            filter_predicate=lambda c: c.partition == DatasetPartition.DEVELOPMENT,
            models_by_id=models_by_id,
        )
        if any(m.sample_count > 0 for m in dev_metrics.values()):
            metrics_by_partition[DatasetPartition.DEVELOPMENT.value] = dev_metrics

        # 2. HELD_OUT
        held_metrics = self._compute_partition_metrics(
            methods_to_run=methods_to_run,
            method_predictions=method_predictions,
            partition=DatasetPartition.HELD_OUT,
            filter_predicate=lambda c: c.partition == DatasetPartition.HELD_OUT,
            models_by_id=models_by_id,
        )
        if any(m.sample_count > 0 for m in held_metrics.values()):
            metrics_by_partition[DatasetPartition.HELD_OUT.value] = held_metrics

        # 3. ALL_CASES (Overall demonstration summary)
        all_metrics = self._compute_partition_metrics(
            methods_to_run=methods_to_run,
            method_predictions=method_predictions,
            partition=DatasetPartition.ALL_CASES,
            filter_predicate=lambda c: True,
            models_by_id=models_by_id,
        )
        metrics_by_partition[DatasetPartition.ALL_CASES.value] = all_metrics

        # Primary metrics_by_method: use requested partition if specified, else ALL_CASES summary
        if target_partition == DatasetPartition.DEVELOPMENT:
            metrics_by_method = dev_metrics
        elif target_partition == DatasetPartition.HELD_OUT:
            metrics_by_method = held_metrics
        else:
            metrics_by_method = all_metrics

        # Slices: By domain
        domains = sorted({c.domain for c in cases_to_evaluate})
        metrics_by_domain: dict[str, dict[str, Any]] = {}
        for d in domains:
            metrics_by_domain[d] = {}
            for m in methods_to_run:
                d_pairs = [(c, p) for c, p in method_predictions[m] if c.domain == d]
                metrics_by_domain[d][m.value] = (
                    ResearchMetricsCalculator.calculate_binary_metrics(
                        d_pairs
                    ).model_dump(mode="json")
                )

        # Slices: By mutation family
        mutations = sorted(
            {c.ground_truth.mutation_family for c in cases_to_evaluate},
            key=lambda x: x.value,
        )
        metrics_by_mutation: dict[str, dict[str, Any]] = {}
        for mut in mutations:
            metrics_by_mutation[mut.value] = {}
            for m in methods_to_run:
                mut_pairs = [
                    (c, p)
                    for c, p in method_predictions[m]
                    if c.ground_truth.mutation_family == mut
                ]
                metrics_by_mutation[mut.value][m.value] = (
                    ResearchMetricsCalculator.calculate_binary_metrics(
                        mut_pairs
                    ).model_dump(mode="json")
                )

        # Slices: By execution provenance
        provenances = sorted(
            {c.execution_provenance.actual_execution_origin for c in cases_to_evaluate}
        )
        metrics_by_prov: dict[str, dict[str, Any]] = {}
        for prov in provenances:
            metrics_by_prov[prov] = {}
            for m in methods_to_run:
                prov_pairs = [
                    (c, p)
                    for c, p in method_predictions[m]
                    if c.execution_provenance.actual_execution_origin == prov
                ]
                metrics_by_prov[prov][m.value] = (
                    ResearchMetricsCalculator.calculate_binary_metrics(
                        prov_pairs
                    ).model_dump(mode="json")
                )

        # Acceptance Criteria targets evaluation across all methods
        (
            b4_results,
            results_by_method,
            notes_by_method,
            b4_notes,
        ) = self._evaluate_acceptance_targets_all_methods(
            metrics_by_method=metrics_by_method,
            test_validity_rate=validity_rate,
        )

        report = ExperimentComparisonReport(
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.version,
            project_id=manifest.project_id,
            created_at=datetime.now(UTC),
            generated_test_validity_rate=validity_rate,
            generated_test_validity_status=validity_status,
            valid_test_count=valid_cases,
            total_test_count=total_cases,
            metrics_by_partition=metrics_by_partition,
            metrics_by_method=metrics_by_method,
            metrics_by_domain=metrics_by_domain,
            metrics_by_mutation=metrics_by_mutation,
            metrics_by_provenance=metrics_by_prov,
            acceptance_criteria_results=b4_results,
            acceptance_criteria_by_method=results_by_method,
            acceptance_notes_by_method=notes_by_method,
            acceptance_notes=b4_notes,
        )

        return report, db_case_results

    def _compute_partition_metrics(
        self,
        methods_to_run: list[BaselineType],
        method_predictions: dict[
            BaselineType,
            list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
        ],
        partition: DatasetPartition,
        filter_predicate: Any,
        models_by_id: dict[str, EFSMModelDefinition],
    ) -> dict[str, MethodResearchMetrics]:
        """Compute metrics for a specific dataset partition."""
        results: dict[str, MethodResearchMetrics] = {}
        for m in methods_to_run:
            pairs = [(c, p) for c, p in method_predictions[m] if filter_predicate(c)]
            timings = [p.evaluator_timing_ms for _, p in pairs]
            med_ms = round(statistics.median(timings), 3) if timings else 0.0
            if timings:
                s_timings = sorted(timings)
                p95_idx = max(
                    0, min(len(s_timings) - 1, math.ceil(0.95 * len(s_timings)) - 1)
                )
                p95_ms = round(s_timings[p95_idx], 3)
            else:
                p95_ms = 0.0

            cov_metrics = None
            if m == BaselineType.B4_FULL_C2 and pairs:
                cov_metrics = self._aggregate_b4_coverage(pairs, models_by_id)

            results[m.value] = ResearchMetricsCalculator.calculate_method_metrics(
                method_id=m,
                method_name=m.value,
                partition=partition,
                case_pairs=pairs,
                overhead_median_ms=med_ms,
                overhead_p95_ms=p95_ms,
                coverage_metrics=cov_metrics,
            )
        return results

    def _aggregate_b4_coverage(
        self,
        pairs: list[tuple[ExperimentCaseRecord, BaselinePredictionContract]],
        models_by_id: dict[str, EFSMModelDefinition],
    ) -> dict[str, Any]:
        """Aggregate coverage metrics for B4 full evaluator across evaluated cases using real target sets."""
        from app.components.c2_state_aware_workflow.evaluator.coverage import (
            ObservedCoverageEngine,
        )

        model_coverages: dict[str, list[Any]] = {}
        for case, pred in pairs:
            if pred.detailed_coverage is not None:
                model_coverages.setdefault(case.model_id, []).append(
                    pred.detailed_coverage
                )

        detailed_by_model: dict[str, Any] = {}
        total_trans_num = 0
        total_trans_den = 0
        total_guard_num = 0
        total_guard_den = 0
        total_path_num = 0
        total_path_den = 0
        total_effect_num = 0
        total_effect_den = 0

        for mid, model in models_by_id.items():
            covs = model_coverages.get(mid, [])
            if not covs:
                continue
            agg_cov = ObservedCoverageEngine.aggregate_suite_coverage(model, covs)
            detailed_by_model[mid] = agg_cov

            total_trans_num += agg_cov.transition_coverage.numerator
            total_trans_den += agg_cov.transition_coverage.denominator
            total_guard_num += agg_cov.guard_outcome_coverage.numerator
            total_guard_den += agg_cov.guard_outcome_coverage.denominator
            total_path_num += agg_cov.selected_path_coverage.numerator
            total_path_den += agg_cov.selected_path_coverage.denominator
            total_effect_num += agg_cov.state_effect_coverage.numerator
            total_effect_den += agg_cov.state_effect_coverage.denominator

        trans_cov = (
            round(total_trans_num / total_trans_den, 4) if total_trans_den > 0 else None
        )
        guard_cov = (
            round(total_guard_num / total_guard_den, 4) if total_guard_den > 0 else None
        )
        path_cov = (
            round(total_path_num / total_path_den, 4) if total_path_den > 0 else None
        )
        effect_cov = (
            round(total_effect_num / total_effect_den, 4)
            if total_effect_den > 0
            else None
        )

        primary_cov = (
            next(iter(detailed_by_model.values())) if detailed_by_model else None
        )

        return {
            "transition_coverage": trans_cov,
            "guard_outcome_coverage": guard_cov,
            "selected_path_coverage": path_cov,
            "state_effect_coverage": effect_cov,
            "detailed_coverage": primary_cov,
            "detailed_coverage_by_model": detailed_by_model,
        }

    def _evaluate_acceptance_targets_all_methods(
        self,
        metrics_by_method: dict[str, MethodResearchMetrics],
        test_validity_rate: float | None,
    ) -> tuple[
        dict[str, bool],
        dict[str, dict[str, bool | None]],
        dict[str, list[str]],
        list[str],
    ]:
        """Evaluate proposal acceptance targets for every method individually and return B4 compatibility results."""
        results_by_method: dict[str, dict[str, bool | None]] = {}
        notes_by_method: dict[str, list[str]] = {}

        for m_id, m_metrics in metrics_by_method.items():
            det = m_metrics.detection_metrics
            loc = m_metrics.localization_metrics
            m_res: dict[str, bool | None] = {}
            m_notes: list[str] = []

            # Target 1: Precision >= 0.85
            p_ok = (det.precision >= 0.85) if det.precision is not None else None
            m_res["target_precision_ge_0_85"] = p_ok
            m_notes.append(
                f"Precision: {det.precision} (target >= 0.85, passed: {p_ok})"
            )

            # Target 2: Recall >= 0.85
            r_ok = (det.recall >= 0.85) if det.recall is not None else None
            m_res["target_recall_ge_0_85"] = r_ok
            m_notes.append(f"Recall: {det.recall} (target >= 0.85, passed: {r_ok})")

            # Target 3: F1 >= 0.85
            f1_ok = (det.f1_score >= 0.85) if det.f1_score is not None else None
            m_res["target_f1_ge_0_85"] = f1_ok
            m_notes.append(
                f"F1 Score: {det.f1_score} (target >= 0.85, passed: {f1_ok})"
            )

            # Target 4: First-divergence accuracy >= 0.80
            if not loc.can_localize:
                m_res["target_localization_accuracy_ge_0_80"] = None
                m_notes.append(
                    "First-Divergence Accuracy: None (unavailable: baseline does not support localization)"
                )
            else:
                loc_ok = (loc.accuracy >= 0.80) if loc.accuracy is not None else None
                m_res["target_localization_accuracy_ge_0_80"] = loc_ok
                m_notes.append(
                    f"First-Divergence Accuracy: {loc.accuracy} (target >= 0.80, passed: {loc_ok})"
                )

            # Target 5: Mutation detection >= 0.85
            mut_ok = (
                (det.mutation_detection_score >= 0.85)
                if det.mutation_detection_score is not None
                else None
            )
            m_res["target_mutation_detection_ge_0_85"] = mut_ok
            m_notes.append(
                f"Mutation Detection: {det.mutation_detection_score} (target >= 0.85, passed: {mut_ok})"
            )

            # Target 6: State-effect fault detection >= 0.85
            eff_ok = (
                (det.state_effect_fault_detection_score >= 0.85)
                if det.state_effect_fault_detection_score is not None
                else None
            )
            m_res["target_state_effect_fault_detection_ge_0_85"] = eff_ok
            m_notes.append(
                f"State-Effect Fault Detection: {det.state_effect_fault_detection_score} (target >= 0.85, passed: {eff_ok})"
            )

            # Target 7: Generated test validity >= 0.90
            val_ok = (
                (test_validity_rate >= 0.90) if test_validity_rate is not None else None
            )
            m_res["target_test_validity_ge_0_90"] = val_ok
            m_notes.append(
                f"Generated-Test Validity Rate: {test_validity_rate} (target >= 0.90, passed: {val_ok})"
            )

            # Target 8: Inconclusive rate <= 0.10
            inc_ok = (
                (det.inconclusive_rate <= 0.10)
                if det.inconclusive_rate is not None
                else None
            )
            m_res["target_inconclusive_rate_le_0_10"] = inc_ok
            m_notes.append(
                f"Inconclusive Rate: {det.inconclusive_rate} (aim <= 0.10, passed: {inc_ok})"
            )

            results_by_method[m_id] = m_res
            notes_by_method[m_id] = m_notes

        b4_key = BaselineType.B4_FULL_C2.value
        b4_results = {
            k: bool(v)
            for k, v in results_by_method.get(b4_key, {}).items()
            if v is not None
        }
        b4_notes = notes_by_method.get(b4_key, [])
        return b4_results, results_by_method, notes_by_method, b4_notes
