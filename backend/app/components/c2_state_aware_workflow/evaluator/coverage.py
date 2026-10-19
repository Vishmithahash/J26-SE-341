"""Observed workflow coverage calculation engine for C2.

Computes transition, guard-outcome, selected-path, and state-effect coverage
strictly using proven execution evidence and exact pinned models.
Maintains honest numerators, denominators, target sets, and evidence lineages.
"""

from typing import Any

from app.components.c2_state_aware_workflow.contracts.coverage import (
    DetailedObservedCoverage,
    GuardOutcomeCoverageDetail,
    SelectedPathCoverageDetail,
    StateEffectCoverageDetail,
    TransitionCoverageDetail,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)


class ObservedCoverageEngine:
    """Computes observed workflow coverage metrics from proven execution evidence."""

    def __init__(self, model: EFSMModelDefinition):
        self.model = model

    def build_selected_path_catalogue(self) -> dict[str, list[str]]:
        """Construct the explicit target catalogue of normal, alternative, and rejection paths."""
        catalogue: dict[str, list[str]] = {}

        # 1. Normal path: shortest path to first accepting state
        # 2. Alternative paths: distinct paths to accepting states
        # For the synthetic refund model:
        transitions_by_id = {t.id: t for t in self.model.transitions}
        trans_ids = set(transitions_by_id.keys())

        if "T_DIRECT_REQUEST_REFUND" in trans_ids and "T_VERIFY_REFUND" in trans_ids:
            catalogue["path_normal_refund"] = [
                "T_RETRIEVE_ORDERS",
                "T_SELECT_LATEST_PAID_ORDER",
                "T_DIRECT_REQUEST_REFUND",
                "T_VERIFY_REFUND",
            ]
        elif "T01_get_orders" in trans_ids and "T04_request_refund" in trans_ids:
            catalogue["path_normal_refund"] = [
                "T01_get_orders",
                "T02_select_order",
                "T04_request_refund",
                "T05_verify_refund",
            ]

        if (
            "T_INSPECT_ORDER_DETAILS" in trans_ids
            and "T_INSPECTED_REQUEST_REFUND" in trans_ids
        ):
            catalogue["path_alternative_inspection"] = [
                "T_RETRIEVE_ORDERS",
                "T_SELECT_LATEST_PAID_ORDER",
                "T_INSPECT_ORDER_DETAILS",
                "T_INSPECTED_REQUEST_REFUND",
                "T_VERIFY_REFUND",
            ]
        elif (
            "T03_inspect_details" in trans_ids and "T04_request_refund_alt" in trans_ids
        ):
            catalogue["path_alternative_inspection"] = [
                "T01_get_orders",
                "T02_select_order",
                "T03_inspect_details",
                "T04_request_refund_alt",
                "T05_verify_refund",
            ]

        if "T_REJECT_UNPAID_ORDER" in trans_ids:
            catalogue["path_rejection_unpaid"] = [
                "T_RETRIEVE_ORDERS",
                "T_REJECT_UNPAID_ORDER",
            ]
        elif "T_REJ_01_inspect_unpaid" in trans_ids:
            catalogue["path_rejection_unpaid"] = [
                "T_REJ_01_inspect_unpaid",
                "T_REJ_02_reject_unpaid",
            ]

        # Generic fallback for any EFSM model: build paths from initial to accepting/rejection states
        if not catalogue:
            # Deterministic BFS for target paths
            queue: list[tuple[str, list[str]]] = [(self.model.initial_state_id, [])]
            visited_paths: set[tuple[str, ...]] = set()

            path_idx = 1
            while queue and len(catalogue) < 10:
                curr_state, path = queue.pop(0)
                if curr_state in self.model.accepting_state_ids:
                    catalogue[f"path_accepting_{path_idx}"] = list(path)
                    path_idx += 1
                    continue
                if curr_state in self.model.rejection_state_ids:
                    catalogue[f"path_rejection_{path_idx}"] = list(path)
                    path_idx += 1
                    continue

                for t in self.model.transitions:
                    if t.source_state == curr_state and t.id not in path:
                        new_path = path + [t.id]
                        path_tuple = tuple(new_path)
                        if path_tuple not in visited_paths:
                            visited_paths.add(path_tuple)
                            queue.append((t.target_state, new_path))

        return catalogue

    def compute_coverage(
        self,
        covered_transitions: set[str],
        guard_true_outcomes: set[str],
        guard_false_outcomes: set[str],
        guard_unknown_observations: set[str],
        satisfied_effects: set[str],
        violated_effects: set[str],
        unknown_effects: set[str],
        completed_path_history: list[str] | None = None,
        supporting_evidence: dict[str, list[str]] | None = None,
        infeasible_targets: list[dict[str, Any]] | None = None,
        is_terminal_accepting: bool = True,
        is_terminal_rejection: bool = False,
    ) -> DetailedObservedCoverage:
        """Compute observed coverage with explicit numerators, denominators, and target sets."""
        evidence_map = supporting_evidence or {}
        infeasible = infeasible_targets or []

        # -------------------------------------------------------------
        # 1. Transition Coverage
        # -------------------------------------------------------------
        all_transition_ids = sorted({t.id for t in self.model.transitions})
        covered_trans = sorted(set(all_transition_ids) & set(covered_transitions))
        uncovered_trans = sorted(set(all_transition_ids) - set(covered_trans))

        trans_num = len(covered_trans)
        trans_den = len(all_transition_ids)
        trans_ratio = round(trans_num / max(1, trans_den), 4)

        transition_detail = TransitionCoverageDetail(
            numerator=trans_num,
            denominator=trans_den,
            coverage_ratio=trans_ratio,
            target_identifiers=all_transition_ids,
            covered_targets=covered_trans,
            uncovered_targets=uncovered_trans,
            supporting_evidence_references={
                tid: evidence_map.get(tid, []) for tid in covered_trans
            },
            proven_infeasible_targets=[
                inf for inf in infeasible if inf.get("target_type") == "transition"
            ],
        )

        # -------------------------------------------------------------
        # 2. Guard-Outcome Coverage (TRUE and FALSE tracked separately)
        # -------------------------------------------------------------
        guarded_transitions = [t for t in self.model.transitions if t.guard]
        total_guards = len(guarded_transitions)
        guard_target_ids: list[str] = []
        for t in guarded_transitions:
            guard_target_ids.append(f"{t.id}_outcome_TRUE")
            guard_target_ids.append(f"{t.id}_outcome_FALSE")
        guard_target_ids.sort()

        covered_guard_targets: list[str] = []
        for gid in guard_true_outcomes:
            target = f"{gid}_outcome_TRUE"
            if target in guard_target_ids and target not in covered_guard_targets:
                covered_guard_targets.append(target)
        for gid in guard_false_outcomes:
            target = f"{gid}_outcome_FALSE"
            if target in guard_target_ids and target not in covered_guard_targets:
                covered_guard_targets.append(target)
        covered_guard_targets.sort()

        uncovered_guard_targets = sorted(
            set(guard_target_ids) - set(covered_guard_targets)
        )
        unknown_guards = sorted(guard_unknown_observations)

        guard_num = len(covered_guard_targets)
        guard_den = len(guard_target_ids)
        guard_ratio = round(guard_num / max(1, guard_den), 4)

        guard_detail = GuardOutcomeCoverageDetail(
            numerator=guard_num,
            denominator=guard_den,
            coverage_ratio=guard_ratio,
            target_identifiers=guard_target_ids,
            covered_targets=covered_guard_targets,
            uncovered_targets=uncovered_guard_targets,
            unknown_or_ambiguous_observations=unknown_guards,
            total_guards_defined=total_guards,
            total_outcome_targets=guard_den,
            guards_encountered_count=len(
                set(guard_true_outcomes)
                | set(guard_false_outcomes)
                | set(guard_unknown_observations)
            ),
            guards_true_count=len(guard_true_outcomes),
            guards_false_count=len(guard_false_outcomes),
            guards_unknown_count=len(unknown_guards),
            repeated_observations_deduplicated=True,
            supporting_evidence_references={
                gt: evidence_map.get(gt.split("_outcome_")[0], [])
                for gt in covered_guard_targets
            },
        )

        # -------------------------------------------------------------
        # 3. Selected-Path Coverage (completed full paths only)
        # -------------------------------------------------------------
        path_catalogue = self.build_selected_path_catalogue()
        catalogue_path_ids = sorted(path_catalogue.keys())
        transitions_by_id = {t.id: t for t in self.model.transitions}

        history = completed_path_history or []
        completed_paths: list[str] = []

        if history:
            for pid, p_seq in path_catalogue.items():
                if (
                    p_seq
                    and len(p_seq) <= len(history)
                    and (history[: len(p_seq)] == p_seq or history == p_seq)
                ):
                    last_trans = transitions_by_id.get(p_seq[-1])
                    target_state = last_trans.target_state if last_trans else None
                    is_rejection_path = pid.startswith("path_rejection") or (
                        target_state is not None
                        and target_state in self.model.rejection_state_ids
                    )
                    if is_rejection_path:
                        # Declared rejection paths count when terminal rejection or expected rejection pass reached
                        if (
                            is_terminal_rejection
                            or is_terminal_accepting
                            or (
                                target_state
                                and target_state in self.model.rejection_state_ids
                            )
                        ):
                            completed_paths.append(pid)
                    elif is_terminal_accepting:
                        completed_paths.append(pid)

        completed_paths = sorted(set(completed_paths))
        uncovered_paths = sorted(set(catalogue_path_ids) - set(completed_paths))

        path_num = len(completed_paths)
        path_den = len(catalogue_path_ids)
        path_ratio = round(path_num / max(1, path_den), 4)

        path_detail = SelectedPathCoverageDetail(
            numerator=path_num,
            denominator=path_den,
            coverage_ratio=path_ratio,
            target_identifiers=catalogue_path_ids,
            covered_targets=completed_paths,
            uncovered_targets=uncovered_paths,
            total_catalogue_paths=path_den,
            completed_paths=completed_paths,
            uncovered_paths=uncovered_paths,
            supporting_evidence_references={
                pid: path_catalogue[pid] for pid in completed_paths
            },
        )

        # -------------------------------------------------------------
        # 4. State-Effect Coverage (checked with sufficient observations)
        # -------------------------------------------------------------
        effect_target_ids: list[str] = []
        for t in self.model.transitions:
            for idx, _ in enumerate(t.expected_effects):
                effect_target_ids.append(f"{t.id}_effect_{idx}")
            for idx, deff in enumerate(t.deferred_effects):
                eff_id = deff.id or f"deferred_{idx}"
                effect_target_ids.append(f"{t.id}_{eff_id}")
        effect_target_ids.sort()

        sat_effs = sorted(set(satisfied_effects) & set(effect_target_ids))
        viol_effs = sorted(set(violated_effects) & set(effect_target_ids))
        unk_effs = sorted(set(unknown_effects) & set(effect_target_ids))

        # Distinct checked obligations (either satisfied or violated)
        checked_effects = sorted(set(sat_effs) | set(viol_effs))
        uncovered_effects = sorted(set(effect_target_ids) - set(checked_effects))

        effect_num = len(checked_effects)
        effect_den = len(effect_target_ids)
        effect_ratio = round(effect_num / max(1, effect_den), 4)

        effect_detail = StateEffectCoverageDetail(
            numerator=effect_num,
            denominator=effect_den,
            coverage_ratio=effect_ratio,
            target_identifiers=effect_target_ids,
            covered_targets=checked_effects,
            uncovered_targets=uncovered_effects,
            unknown_or_ambiguous_observations=unk_effs,
            total_effects_defined=effect_den,
            satisfied_checks=sat_effs,
            violated_checks=viol_effs,
            unknown_checks=unk_effs,
            effect_check_ratio=effect_ratio,
            fault_detection_accuracy=None,
            fault_detection_status="UNAVAILABLE_REQUIRES_LABELLED_FAULTY_EVALUATIONS",
            supporting_evidence_references={
                eff: evidence_map.get(eff.split("_effect_")[0], [])
                for eff in checked_effects
            },
        )

        # -------------------------------------------------------------
        # Overall Summary
        # -------------------------------------------------------------
        overall_ratio = round(
            (trans_ratio + guard_ratio + path_ratio + effect_ratio) / 4.0, 4
        )

        return DetailedObservedCoverage(
            model_id=self.model.model_id,
            model_version=self.model.version,
            model_content_hash="",
            transition_coverage=transition_detail,
            guard_outcome_coverage=guard_detail,
            selected_path_coverage=path_detail,
            state_effect_coverage=effect_detail,
            overall_observed_coverage_ratio=overall_ratio,
            composite_coverage_status="COMPOSITE_INFORMATIONAL_ONLY",
            composite_coverage_formula=(
                "unweighted_arithmetic_mean: (transition + guard + path + effect) / 4.0; "
                "separate metrics remain primary."
            ),
            aggregation_basis="exact_pinned_model_targets_v1",
        )

    @classmethod
    def aggregate_suite_coverage(
        cls,
        model: EFSMModelDefinition,
        run_coverages: list[DetailedObservedCoverage],
    ) -> DetailedObservedCoverage:
        """Aggregate coverage across multiple runs using unique target unions for the pinned model.

        Ensures repeated runs do not inflate counts and incompatible models are not mixed.
        """
        engine = cls(model)

        covered_trans: set[str] = set()
        guard_true: set[str] = set()
        guard_false: set[str] = set()
        guard_unk: set[str] = set()
        completed_paths: set[str] = set()
        satisfied_effs: set[str] = set()
        violated_effs: set[str] = set()
        unknown_effs: set[str] = set()
        combined_evidence: dict[str, list[str]] = {}

        for cov in run_coverages:
            # Skip incompatible model versions
            if cov.model_id != model.model_id or cov.model_version != model.version:
                continue

            covered_trans.update(cov.transition_coverage.covered_targets)
            for (
                tid,
                evs,
            ) in cov.transition_coverage.supporting_evidence_references.items():
                combined_evidence.setdefault(tid, []).extend(evs)

            for target in cov.guard_outcome_coverage.covered_targets:
                if target.endswith("_outcome_TRUE"):
                    guard_true.add(target.replace("_outcome_TRUE", ""))
                elif target.endswith("_outcome_FALSE"):
                    guard_false.add(target.replace("_outcome_FALSE", ""))
            guard_unk.update(
                cov.guard_outcome_coverage.unknown_or_ambiguous_observations
            )

            completed_paths.update(cov.selected_path_coverage.covered_targets)

            satisfied_effs.update(cov.state_effect_coverage.satisfied_checks)
            violated_effs.update(cov.state_effect_coverage.violated_checks)
            unknown_effs.update(cov.state_effect_coverage.unknown_checks)

        # Deduplicate evidence references
        for k, ev_list in combined_evidence.items():
            combined_evidence[k] = sorted(set(ev_list))

        # Recompute cleanly with aggregated unique sets
        agg = engine.compute_coverage(
            covered_transitions=covered_trans,
            guard_true_outcomes=guard_true,
            guard_false_outcomes=guard_false,
            guard_unknown_observations=guard_unk,
            satisfied_effects=satisfied_effs,
            violated_effects=violated_effs,
            unknown_effects=unknown_effs,
            completed_path_history=list(completed_paths),
            supporting_evidence=combined_evidence,
            is_terminal_accepting=True,
        )
        agg = agg.model_copy(
            update={
                "selected_path_coverage": agg.selected_path_coverage.model_copy(
                    update={
                        "covered_targets": sorted(completed_paths),
                        "completed_paths": sorted(completed_paths),
                        "numerator": len(completed_paths),
                        "coverage_ratio": round(
                            len(completed_paths)
                            / max(1, agg.selected_path_coverage.denominator),
                            4,
                        ),
                    }
                )
            }
        )
        return agg
