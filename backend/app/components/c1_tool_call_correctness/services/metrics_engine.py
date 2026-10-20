import math
import random
from typing import Any

from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
)
from app.components.c1_tool_call_correctness.contracts.research import (
    AccuracyMetricsReport,
    DatasetSplit,
    MetricWithDetail,
    ReferenceLabelRecord,
)
from app.components.c1_tool_call_correctness.contracts.results import CorrectnessVerdict


def _calc_ratio(
    num: int, den: int, formula: str, notes: str = "", default: float = 0.0
) -> MetricWithDetail:
    """Calculates ratio with explicit zero-denominator protection."""
    val = (num / den) if den > 0 else default
    val_rounded = round(val, 4)
    return MetricWithDetail(
        value=val_rounded,
        numerator=num,
        denominator=den,
        formula=formula,
        notes=notes
        if den > 0
        else f"{notes} (Zero denominator; defaulted to {default})".strip(),
    )


def _bootstrap_family_ci(
    data_by_family: dict[str, list[tuple[int, int]]],
    num_bootstrap: int = 500,
    alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    """Calculates cluster-bootstrap 95% confidence intervals by resampling task families with replacement."""
    families = list(data_by_family.keys())
    if len(families) < 2:
        return None, None

    ratios: list[float] = []
    rng = random.Random(42)  # Deterministic seed for reproducible bootstrap

    for _ in range(num_bootstrap):
        sampled_fams = rng.choices(families, k=len(families))
        sample_num = 0
        sample_den = 0
        for f in sampled_fams:
            for n, d in data_by_family[f]:
                sample_num += n
                sample_den += d
        if sample_den > 0:
            ratios.append(sample_num / sample_den)

    if not ratios:
        return None, None

    ratios.sort()
    low_idx = math.floor(len(ratios) * (alpha / 2))
    high_idx = math.ceil(len(ratios) * (1 - alpha / 2)) - 1
    high_idx = min(high_idx, len(ratios) - 1)

    return round(ratios[low_idx], 4), round(ratios[high_idx], 4)


class MetricsEngine:
    """Computes mathematically documented Component 1 accuracy, diagnosis, code localisation,
    evidence link, and correction metrics against independently reviewed reference labels."""

    def compute_metrics(
        self,
        project_id: str,
        run_id: str | None,
        dataset_split: DatasetSplit | None,
        reference_labels: list[ReferenceLabelRecord],
        executions: list[CaseExecutionDetail],
        diagnoses: list[CaseDiagnosisRecord],
        corrections: list[dict[str, Any]],
        declared_testable_requirements: list[str] | None = None,
    ) -> AccuracyMetricsReport:
        """Computes comprehensive accuracy report matching ground truth reference labels."""
        # 1. Index records by case_id
        label_map: dict[str, ReferenceLabelRecord] = {
            lbl.case_id: lbl for lbl in reference_labels
        }
        exec_map: dict[str, CaseExecutionDetail] = {ex.case_id: ex for ex in executions}
        diag_map: dict[str, CaseDiagnosisRecord] = {d.case_id: d for d in diagnoses}

        # Filter by dataset_split if requested
        if dataset_split:
            target_case_ids = {
                lbl.case_id
                for lbl in reference_labels
                if lbl.dataset_split == dataset_split
            }
        else:
            target_case_ids = set(label_map.keys())

        # Grouping for cluster bootstrap: task_family -> list[(num, den)]
        fam_failure_prec: dict[str, list[tuple[int, int]]] = {}
        fam_diag_acc: dict[str, list[tuple[int, int]]] = {}

        # -------------------------------------------------------------
        # Metric 1: Generated-Case Validity
        # num = valid cases (executed or ready without generation validation error)
        # den = total cases
        # -------------------------------------------------------------
        total_eval_cases = len(target_case_ids)
        valid_cases_count = sum(
            1
            for cid in target_case_ids
            if cid in exec_map
            and exec_map[cid].verdict != CorrectnessVerdict.INCONCLUSIVE
        )
        gen_case_validity = _calc_ratio(
            num=valid_cases_count,
            den=total_eval_cases,
            formula="valid_executable_cases / total_generated_cases",
            notes="Proportion of generated candidate cases that passed validation and produced a decisive verdict.",
        )

        # -------------------------------------------------------------
        # Metric 2: Requirement Coverage
        # -------------------------------------------------------------
        declared_reqs = set(declared_testable_requirements or [])
        covered_reqs = set()
        for cid in target_case_ids:
            if cid in exec_map:
                c_exec = exec_map[cid]
                if isinstance(c_exec, dict):
                    for req in c_exec.get("requirement_refs", []) or []:
                        covered_reqs.add(req)
                    for exp in c_exec.get("resolved_expectations", []) or []:
                        if isinstance(exp, dict):
                            for req in exp.get("requirement_refs", []) or []:
                                covered_reqs.add(req)
                        else:
                            for req in getattr(exp, "requirement_refs", []) or []:
                                covered_reqs.add(req)
                else:
                    for req in getattr(c_exec, "requirement_refs", []) or []:
                        covered_reqs.add(req)
                    for exp in getattr(c_exec, "resolved_expectations", []) or []:
                        if isinstance(exp, dict):
                            for req in exp.get("requirement_refs", []) or []:
                                covered_reqs.add(req)
                        else:
                            for req in getattr(exp, "requirement_refs", []) or []:
                                covered_reqs.add(req)
        req_cov_num = (
            len(covered_reqs.intersection(declared_reqs))
            if declared_reqs
            else len(covered_reqs)
        )
        req_cov_den = len(declared_reqs) if declared_reqs else max(len(covered_reqs), 1)
        requirement_coverage = _calc_ratio(
            num=req_cov_num,
            den=req_cov_den,
            formula="covered_testable_requirements / declared_testable_requirements",
            notes="Proportion of declared testable project requirements exercised by executed test cases.",
        )

        # -------------------------------------------------------------
        # Metric 3: Failure Detection Precision & Recall
        # Ground truth positive = FAIL
        # Predicted positive = FAIL
        # -------------------------------------------------------------
        tp, fp, fn, _tn = 0, 0, 0, 0
        inconclusive_count = 0

        for cid in target_case_ids:
            lbl = label_map.get(cid)
            ex = exec_map.get(cid)
            if not lbl or not ex:
                continue

            fam = lbl.task_family
            if fam not in fam_failure_prec:
                fam_failure_prec[fam] = []

            is_gt_fail = lbl.ground_truth_verdict == CorrectnessVerdict.FAIL
            is_pred_fail = ex.verdict == CorrectnessVerdict.FAIL
            is_pred_inconclusive = ex.verdict == CorrectnessVerdict.INCONCLUSIVE

            if is_pred_inconclusive:
                inconclusive_count += 1

            if is_gt_fail and is_pred_fail:
                tp += 1
                fam_failure_prec[fam].append((1, 1))
            elif not is_gt_fail and is_pred_fail:
                fp += 1
                fam_failure_prec[fam].append((0, 1))
            elif is_gt_fail and not is_pred_fail:
                fn += 1
            else:
                _tn += 1

        failure_precision = _calc_ratio(
            num=tp,
            den=tp + fp,
            formula="TP_fail / (TP_fail + FP_fail)",
            notes="Precision of flagging tool-call correctness failures.",
        )
        ci_prec_low, ci_prec_high = _bootstrap_family_ci(fam_failure_prec)
        failure_precision.ci_95_lower = ci_prec_low
        failure_precision.ci_95_upper = ci_prec_high

        failure_recall = _calc_ratio(
            num=tp,
            den=tp + fn,
            formula="TP_fail / (TP_fail + FN_fail)",
            notes="Recall of true tool-call correctness failures.",
        )

        inconclusive_rate = _calc_ratio(
            num=inconclusive_count,
            den=total_eval_cases,
            formula="inconclusive_cases / total_cases",
            notes="Rate of inconclusive executions requiring manual triage.",
        )

        decision_coverage = _calc_ratio(
            num=total_eval_cases - inconclusive_count,
            den=total_eval_cases,
            formula="(total_cases - inconclusive_cases) / total_cases",
            notes="Proportion of cases receiving an explicit PASS or FAIL verdict.",
        )

        # -------------------------------------------------------------
        # Metric 4: Diagnosis Accuracy & Code Localisation
        # Rule: Unknown diagnosis counts as incorrect when independent cause is known.
        # Top-1 and Top-3 code localisation calculated ONLY on code defect ground truth.
        # False code-blame calculated ONLY on non-code defect ground truth.
        # -------------------------------------------------------------
        diag_correct_all = 0
        diag_total_labelled = 0
        diag_correct_decided = 0
        diag_total_decided = 0

        code_defect_cases = 0
        top_1_hits = 0
        top_3_hits = 0

        non_code_cases = 0
        false_code_blame_count = 0

        for cid in target_case_ids:
            lbl = label_map.get(cid)
            diag = diag_map.get(cid)

            # Only evaluate failures that have a diagnosed cause
            if not lbl or not lbl.ground_truth_cause:
                continue

            diag_total_labelled += 1
            predicted_cause = diag.cause_category if diag else CauseCategory.UNKNOWN
            fam = lbl.task_family
            if fam not in fam_diag_acc:
                fam_diag_acc[fam] = []

            # All labelled cases: unknown counts as incorrect
            if predicted_cause == lbl.ground_truth_cause:
                diag_correct_all += 1
                fam_diag_acc[fam].append((1, 1))
            else:
                fam_diag_acc[fam].append((0, 1))

            # Decided subset (excluding unknown diagnoses)
            if predicted_cause != CauseCategory.UNKNOWN:
                diag_total_decided += 1
                if predicted_cause == lbl.ground_truth_cause:
                    diag_correct_decided += 1

            # Code localisation check
            if (
                lbl.ground_truth_cause
                == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
            ):
                code_defect_cases += 1
                pred_locs: list[CandidateCodeLocation] = (
                    diag.candidate_code_locations if diag else []
                )
                # Check top 1
                if pred_locs and _matches_ground_truth_loc(
                    pred_locs[0], lbl.ground_truth_code_locations
                ):
                    top_1_hits += 1

                # Check top 3
                if any(
                    _matches_ground_truth_loc(loc, lbl.ground_truth_code_locations)
                    for loc in pred_locs[:3]
                ):
                    top_3_hits += 1

            # False code-blame check on non-code defects
            if (
                lbl.ground_truth_cause
                != CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
            ):
                non_code_cases += 1
                if predicted_cause == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT:
                    false_code_blame_count += 1

        diagnosis_acc_all = _calc_ratio(
            num=diag_correct_all,
            den=diag_total_labelled,
            formula="correct_cause_predictions / total_labelled_failures",
            notes="Diagnosis accuracy across all labelled cases (UNKNOWN counts as incorrect).",
        )
        ci_diag_low, ci_diag_high = _bootstrap_family_ci(fam_diag_acc)
        diagnosis_acc_all.ci_95_lower = ci_diag_low
        diagnosis_acc_all.ci_95_upper = ci_diag_high

        diagnosis_acc_decided = _calc_ratio(
            num=diag_correct_decided,
            den=diag_total_decided,
            formula="correct_cause_predictions / (total_labelled_failures - unknown_diagnoses)",
            notes="Diagnosis accuracy over decisive diagnoses.",
        )

        top_1_loc_acc = _calc_ratio(
            num=top_1_hits,
            den=code_defect_cases,
            formula="top_1_correct_code_locations / total_ground_truth_code_defects",
            notes="Top-1 candidate code location matches ground truth defect.",
        )

        top_3_loc_acc = _calc_ratio(
            num=top_3_hits,
            den=code_defect_cases,
            formula="top_3_correct_code_locations / total_ground_truth_code_defects",
            notes="Top-3 candidate code locations include ground truth defect.",
        )

        false_code_blame = _calc_ratio(
            num=false_code_blame_count,
            den=non_code_cases,
            formula="non_code_failures_classified_as_code_defect / total_non_code_failures",
            notes="Rate of falsely blaming application code for agent or specification defects.",
        )

        # -------------------------------------------------------------
        # Metric 5: Evidence Link Accuracy & Coverage
        # -------------------------------------------------------------
        total_links = 0
        valid_links = 0
        cases_with_valid_links = 0
        total_diagnosed_cases = len(diag_map)

        for cid in target_case_ids:
            lbl = label_map.get(cid)
            diag = diag_map.get(cid)
            if not diag:
                continue

            gt_valid_refs = set(lbl.valid_evidence_refs) if lbl else set()
            case_has_valid = False
            for ref in diag.evidence_refs:
                total_links += 1
                if not gt_valid_refs or ref in gt_valid_refs:
                    valid_links += 1
                    case_has_valid = True

            if case_has_valid:
                cases_with_valid_links += 1

        evidence_link_acc = _calc_ratio(
            num=valid_links,
            den=total_links,
            formula="valid_evidence_references / total_linked_evidence_references",
            notes="Accuracy of evidence references supporting diagnosis.",
        )

        evidence_cov = _calc_ratio(
            num=cases_with_valid_links,
            den=total_diagnosed_cases,
            formula="diagnosed_cases_with_valid_evidence / total_diagnosed_cases",
            notes="Proportion of diagnosed cases backed by valid evidence links.",
        )

        # -------------------------------------------------------------
        # Metric 6: Verification & Candidate Correction Metrics
        # -------------------------------------------------------------
        attempted_count = len(corrections)
        verified_count = sum(1 for c in corrections if c.get("is_verified") is True)
        eligible_failures_count = sum(
            1
            for d in diagnoses
            if d.cause_category == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
        )
        regressions_count = 0
        for c in corrections:
            for v_chk in c.get("verification_results", []):
                if (
                    v_chk.get("step_type") == "RUN_REGRESSION_CHECKS"
                    and v_chk.get("status") == "FAILED"
                ):
                    regressions_count += 1
                    break

        verified_corr_rate = _calc_ratio(
            num=verified_count,
            den=eligible_failures_count,
            formula="verified_corrections / total_eligible_application_code_defects",
            notes="Verified candidate patches achieved over all eligible code defects.",
        )

        verification_success = _calc_ratio(
            num=verified_count,
            den=attempted_count,
            formula="verified_corrections / attempted_corrections",
            notes="Success rate of verification among attempted candidate patches.",
        )

        regression_rate = _calc_ratio(
            num=regressions_count,
            den=attempted_count,
            formula="candidates_causing_regressions / attempted_corrections",
            notes="Rate of candidate patches that introduced regression check failures.",
        )

        # -------------------------------------------------------------
        # Latency statistics
        # -------------------------------------------------------------
        diag_durations = [
            d.duration_ms
            for d in diagnoses
            if hasattr(d, "duration_ms") and d.duration_ms > 0
        ]
        ver_durations = [
            c.get("metrics", {}).get("total_duration_ms", 0.0)
            for c in corrections
            if c.get("metrics", {}).get("total_duration_ms", 0) > 0
        ]

        def _calc_p95(vals: list[float]) -> tuple[float, float]:
            if not vals:
                return 0.0, 0.0
            s = sorted(vals)
            med = s[len(s) // 2]
            p95_idx = min(math.ceil(0.95 * len(s)) - 1, len(s) - 1)
            return round(med, 2), round(s[p95_idx], 2)

        med_diag, p95_diag = _calc_p95(diag_durations)
        med_ver, p95_ver = _calc_p95(ver_durations)

        return AccuracyMetricsReport(
            project_id=project_id,
            run_id=run_id,
            dataset_split=dataset_split,
            total_labelled_cases=len(label_map),
            total_evaluated_cases=total_eval_cases,
            generated_case_validity=gen_case_validity,
            requirement_coverage=requirement_coverage,
            failure_detection_precision=failure_precision,
            failure_detection_recall=failure_recall,
            inconclusive_rate=inconclusive_rate,
            decision_coverage=decision_coverage,
            diagnosis_accuracy_all=diagnosis_acc_all,
            diagnosis_accuracy_decided=diagnosis_acc_decided,
            top_1_code_localisation_accuracy=top_1_loc_acc,
            top_3_code_localisation_accuracy=top_3_loc_acc,
            false_code_blame_rate=false_code_blame,
            evidence_link_accuracy=evidence_link_acc,
            evidence_coverage=evidence_cov,
            verified_correction_rate=verified_corr_rate,
            verification_success_rate=verification_success,
            regression_check_failure_rate=regression_rate,
            median_diagnosis_time_ms=med_diag,
            p95_diagnosis_time_ms=p95_diag,
            median_verification_time_ms=med_ver,
            p95_verification_time_ms=p95_ver,
        )


def _matches_ground_truth_loc(cand: Any, gt_locs: list[Any]) -> bool:
    """Checks if candidate code location matches any ground truth location."""
    c_file = getattr(cand, "file_path", "").replace("\\", "/").strip()
    c_fn = getattr(cand, "function_name", None)

    for gt in gt_locs:
        gt_file = (
            (gt.file_path if hasattr(gt, "file_path") else gt.get("file_path", ""))
            .replace("\\", "/")
            .strip()
        )
        gt_fn = (
            gt.function_name
            if hasattr(gt, "function_name")
            else gt.get("function_name")
        )

        if (c_file.endswith(gt_file) or gt_file.endswith(c_file)) and (
            not gt_fn or gt_fn == c_fn
        ):
            return True
    return False


metrics_engine = MetricsEngine()
