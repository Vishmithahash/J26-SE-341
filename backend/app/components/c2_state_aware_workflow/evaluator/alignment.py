"""Trace-to-EFSM alignment engine with non-deterministic branching and failure localisation.

Tracks all currently feasible configurations simultaneously across model states,
runtime variable bindings, guard outcomes, and effect obligations (both immediate
and deferred checkpoint effects).
Localises the earliest proven point of divergence where all candidate model paths
are ruled out by observable evidence.
Robustly handles incomplete evidence: independent violations still establish FAIL
while incomplete evidence without proven violations produces INCONCLUSIVE.
"""

import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.contracts.coverage import (
    DetailedObservedCoverage,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    TransitionDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    FirstDivergenceDetail,
    ViolationDetail,
    ViolationType,
    WorkflowCoverageSummary,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.evaluator.coverage import (
    ObservedCoverageEngine,
)
from app.components.c2_state_aware_workflow.evaluator.normalizer import NormalizedTrace
from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
    evaluate_predicate,
)
from app.components.c2_state_aware_workflow.predicates.tristate import TriState


def _snapshot_value(snapshot: dict[str, Any], path: str) -> Any:
    """Value of a flat key, or of a dotted path in a nested snapshot (None when absent)."""
    if path in snapshot:
        return snapshot[path]
    current: Any = snapshot
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


class FeasibleConfiguration(BaseModel):
    """A feasible active configuration during trace-to-EFSM alignment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_state_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    path_history: list[str] = Field(default_factory=list)
    state_history: list[str] = Field(default_factory=list)
    satisfied_milestones: set[str] = Field(default_factory=set)
    proven_conditions: list[str] = Field(default_factory=list)
    unresolved_conditions: list[str] = Field(default_factory=list)
    pending_effects: list[dict[str, Any]] = Field(default_factory=list)


class AlignmentResult(BaseModel):
    """Outcome of aligning a normalized runtime trace against a reference EFSM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_aligned: bool
    is_inconclusive: bool = False
    inconclusive_reason: str | None = None
    terminal_configurations: list[FeasibleConfiguration] = Field(default_factory=list)
    violations: list[ViolationDetail] = Field(default_factory=list)
    first_divergence: FirstDivergenceDetail | None = None
    divergence_localisation_uncertainty: str | None = None
    observed_states: list[str] = Field(default_factory=list)
    coverage: WorkflowCoverageSummary = Field(default_factory=WorkflowCoverageSummary)
    detailed_coverage: DetailedObservedCoverage | None = None
    observation_limitations: list[str] = Field(default_factory=list)


class TraceToEFSMAlignmentEngine:
    """Non-deterministic, bounded alignment engine with first-divergence localisation."""

    def __init__(self, model: EFSMModelDefinition, max_configurations: int = 200):
        self.model = model
        self.max_configurations = max_configurations
        self.tool_to_transitions: dict[str, list[TransitionDefinition]] = {}
        for t in model.transitions:
            self.tool_to_transitions.setdefault(t.trigger_event, []).append(t)

        self.transitions_by_id = {t.id: t for t in model.transitions}
        self.transitions_by_source: dict[str, list[TransitionDefinition]] = {}
        for t in model.transitions:
            self.transitions_by_source.setdefault(t.source_state, []).append(t)

    def align(
        self,
        trace: NormalizedTrace,
        test_def: GeneratedTestDefinition,
        fixture_data: dict[str, Any] | None = None,
    ) -> AlignmentResult:
        """Align trace events and state observations against the reference EFSM."""
        coverage_engine = ObservedCoverageEngine(self.model)

        # Record evidence incompleteness indicators without premature blanket returns
        evidence_gap_reasons: list[str] = []
        if trace.has_audit_anomalies:
            evidence_gap_reasons.append(
                f"Evidence audit anomalies detected: {'; '.join(trace.diagnostics)}"
            )

        if (
            trace.completeness.is_truncated
            or not trace.completeness.confirmed_agent_termination
        ):
            evidence_gap_reasons.append(
                "Evidence collection stopped or was truncated without confirmed agent termination marker"
            )

        fixture_ctx = fixture_data or test_def.permitted_context.get("fixture", {})

        # Initialise variables from model declarations
        initial_vars: dict[str, Any] = {}
        for v in self.model.variables:
            if v.initial_value is not None:
                initial_vars[v.name] = copy.deepcopy(v.initial_value)

        # Dynamic entity binding from fixture context if provided
        if "customer_id" in fixture_ctx:
            initial_vars["requesting_customer_id"] = fixture_ctx["customer_id"]

        if "orders" in fixture_ctx and isinstance(fixture_ctx["orders"], (list, dict)):
            raw_orders = fixture_ctx["orders"]
            if isinstance(raw_orders, dict):
                orders_list = []
                for k, v in raw_orders.items():
                    if isinstance(v, dict):
                        item = copy.deepcopy(v)
                        if "order_id" not in item and "id" not in item:
                            try:
                                item["order_id"] = int(k)
                            except ValueError:
                                item["order_id"] = k
                        orders_list.append(item)
                    else:
                        orders_list.append(v)
            else:
                orders_list = list(raw_orders)

            paid_orders = [
                o
                for o in orders_list
                if isinstance(o, dict)
                and (o.get("payment_status") == "PAID" or o.get("status") == "PAID")
            ]
            if paid_orders:
                paid_orders.sort(
                    key=lambda x: str(x.get("ordered_at") or x.get("created_at") or ""),
                    reverse=True,
                )
                detected_id = paid_orders[0].get("order_id") or paid_orders[0].get("id")
                if detected_id is not None:
                    initial_vars["target_latest_order_id"] = detected_id

        # Initialize configurations with initial state
        active_configs: list[FeasibleConfiguration] = [
            FeasibleConfiguration(
                current_state_id=self.model.initial_state_id,
                variables=initial_vars,
                path_history=[],
                state_history=[self.model.initial_state_id],
                satisfied_milestones=set(),
                proven_conditions=[],
                unresolved_conditions=[],
                pending_effects=[],
            )
        ]

        # Rich coverage tracking structures
        covered_transitions: set[str] = set()
        guard_true_outcomes: set[str] = set()
        guard_false_outcomes: set[str] = set()
        guard_unknown_observations: set[str] = set()
        satisfied_effects: set[str] = set()
        violated_effects: set[str] = set()
        unknown_effects: set[str] = set()
        supporting_evidence: dict[str, list[str]] = {}
        observation_limitations: list[str] = []

        reached_milestones: set[str] = set()
        observed_states_sequence: list[str] = [self.model.initial_state_id]

        # Process events step by step
        for i, event in enumerate(trace.ordered_events):
            next_configs: list[FeasibleConfiguration] = []
            obs = trace.state_observations_by_index.get(event.event_index)

            if obs is None:
                gap_msg = f"Missing state snapshot for event index {event.event_index} ('{event.tool_name}')"
                evidence_gap_reasons.append(gap_msg)
                observation_limitations.append(gap_msg)

            # Advance each active configuration
            for config in active_configs:
                curr_state = config.current_state_id
                possible_transitions = self.transitions_by_source.get(curr_state, [])

                # Match by tool name / action
                matching_transitions = [
                    t
                    for t in possible_transitions
                    if t.trigger_event == event.tool_name
                ]

                for trans in matching_transitions:
                    # 1. Entity Continuity Check
                    entity_mismatch = False
                    if (
                        "order_id" in event.arguments
                        and "selected_order_id" in config.variables
                    ):
                        expected_oid = config.variables["selected_order_id"]
                        actual_oid = event.arguments["order_id"]
                        if expected_oid is not None and actual_oid != expected_oid:
                            entity_mismatch = True

                    if entity_mismatch:
                        continue  # Prune branch due to entity mismatch

                    # 2. Guard evaluation with Kleene logic
                    guard_sat = TriState.TRUE
                    if trans.guard:
                        if obs is not None:
                            eval_ctx = EvaluationContext(
                                event={
                                    "name": event.tool_name,
                                    "arguments": event.arguments,
                                    "result": event.observable_result,
                                },
                                variables=copy.deepcopy(config.variables),
                                fixture=fixture_ctx,
                                before=obs.before_state,
                                after=obs.after_state,
                            )
                            try:
                                guard_sat = evaluate_predicate(trans.guard, eval_ctx)
                            except Exception:  # noqa: BLE001
                                guard_sat = TriState.UNKNOWN
                        else:
                            # State snapshot missing -> guard evaluates to UNKNOWN
                            guard_sat = TriState.UNKNOWN

                    # TriState.FALSE strictly prunes candidate transition
                    if guard_sat == TriState.FALSE:
                        guard_false_outcomes.add(trans.id)
                        continue

                    if trans.guard:
                        if guard_sat == TriState.TRUE:
                            guard_true_outcomes.add(trans.id)
                        elif guard_sat == TriState.UNKNOWN:
                            guard_unknown_observations.add(trans.id)

                    # 3. Apply transition updates to runtime variables
                    next_vars = copy.deepcopy(config.variables)
                    update_ctx = EvaluationContext(
                        event={
                            "arguments": event.arguments,
                            "result": event.observable_result,
                        },
                        variables=next_vars,
                        fixture=fixture_ctx,
                        before=obs.before_state if obs else {},
                        after=obs.after_state if obs else {},
                    )
                    for action in trans.actions:
                        update_ctx.apply_update(action)

                    if (
                        event.tool_name == "select_order"
                        and "order_id" in event.arguments
                    ):
                        next_vars["selected_order_id"] = event.arguments["order_id"]

                    # 4. Immediate expected state effects
                    effects_ok = True
                    if obs is not None:
                        for idx, eff in enumerate(trans.expected_effects):
                            eff_key = f"{trans.id}_effect_{idx}"
                            eff_ctx = EvaluationContext(
                                event={
                                    "arguments": event.arguments,
                                    "result": event.observable_result,
                                },
                                variables=next_vars,
                                fixture=fixture_ctx,
                                before=obs.before_state,
                                after=obs.after_state,
                            )
                            try:
                                res = evaluate_predicate(eff, eff_ctx)
                                if res == TriState.TRUE:
                                    satisfied_effects.add(eff_key)
                                elif res == TriState.FALSE:
                                    violated_effects.add(eff_key)
                                    effects_ok = False
                                    break
                                else:
                                    unknown_effects.add(eff_key)
                            except Exception:  # noqa: BLE001
                                unknown_effects.add(eff_key)
                    else:
                        for idx, _ in enumerate(trans.expected_effects):
                            unknown_effects.add(f"{trans.id}_effect_{idx}")

                    if not effects_ok:
                        continue  # Immediate state effect failed

                    # 5. Deferred effects registration and checkpoint verification
                    next_pending_effects = list(config.pending_effects)
                    for deff in getattr(trans, "deferred_effects", []):
                        next_pending_effects.append(
                            {
                                "id": deff.id,
                                "predicate": deff.predicate,
                                "checkpoint_state_id": deff.checkpoint_state_id,
                                "source_transition": trans.id,
                            }
                        )

                    # Check any pending effects whose checkpoint matches target_state
                    deferred_effects_ok = True
                    if obs is not None:
                        for pe in list(next_pending_effects):
                            if pe["checkpoint_state_id"] == trans.target_state:
                                eff_id = pe.get("id") or "deferred"
                                pe_key = f"{pe['source_transition']}_{eff_id}"
                                chk_ctx = EvaluationContext(
                                    event={
                                        "arguments": event.arguments,
                                        "result": event.observable_result,
                                    },
                                    variables=next_vars,
                                    fixture=fixture_ctx,
                                    before=obs.before_state,
                                    after=obs.after_state,
                                )
                                try:
                                    pe_res = evaluate_predicate(
                                        pe["predicate"], chk_ctx
                                    )
                                    if pe_res == TriState.TRUE:
                                        satisfied_effects.add(pe_key)
                                        next_pending_effects.remove(pe)
                                    elif pe_res == TriState.FALSE:
                                        violated_effects.add(pe_key)
                                        # Proven missing effect at designated checkpoint
                                        deferred_effects_ok = False
                                        break
                                    else:
                                        # UNKNOWN: missing observation evidence at checkpoint
                                        unknown_effects.add(pe_key)
                                        observation_limitations.append(
                                            f"Missing observation evidence for deferred effect '{pe_key}' at checkpoint '{trans.target_state}'."
                                        )
                                except Exception:  # noqa: BLE001
                                    unknown_effects.add(pe_key)

                    if not deferred_effects_ok:
                        continue

                    # 6. Check workflow invariants
                    invariants_ok = True
                    if obs is not None:
                        for inv in self.model.invariants:
                            inv_ctx = EvaluationContext(
                                variables=next_vars,
                                fixture=fixture_ctx,
                                before=obs.before_state,
                                after=obs.after_state,
                            )
                            try:
                                res = evaluate_predicate(inv.predicate, inv_ctx)
                                if res == TriState.FALSE:
                                    invariants_ok = False
                                    break
                            except Exception:  # noqa: BLE001, S110
                                pass

                    if not invariants_ok:
                        continue

                    # Record covered elements
                    covered_transitions.add(trans.id)
                    supporting_evidence.setdefault(trans.id, []).append(event.event_id)

                    new_milestones = set(config.satisfied_milestones)
                    for ms in self.model.milestones:
                        if ms.state_id == trans.target_state:
                            new_milestones.add(ms.id)
                            reached_milestones.add(ms.id)

                    next_configs.append(
                        FeasibleConfiguration(
                            current_state_id=trans.target_state,
                            variables=next_vars,
                            path_history=config.path_history + [trans.id],
                            state_history=config.state_history + [trans.target_state],
                            satisfied_milestones=new_milestones,
                            proven_conditions=config.proven_conditions
                            + ([f"Guard on {trans.id} TRUE"] if trans.guard else []),
                            unresolved_conditions=config.unresolved_conditions
                            + (
                                [f"Guard on {trans.id} UNKNOWN"]
                                if guard_sat == TriState.UNKNOWN
                                else []
                            ),
                            pending_effects=next_pending_effects,
                        )
                    )

            # Check configuration limit (branch budget)
            if len(next_configs) > self.max_configurations:
                det_cov = coverage_engine.compute_coverage(
                    covered_transitions=covered_transitions,
                    guard_true_outcomes=guard_true_outcomes,
                    guard_false_outcomes=guard_false_outcomes,
                    guard_unknown_observations=guard_unknown_observations,
                    satisfied_effects=satisfied_effects,
                    violated_effects=violated_effects,
                    unknown_effects=unknown_effects,
                    completed_path_history=active_configs[0].path_history
                    if active_configs
                    else [],
                    supporting_evidence=supporting_evidence,
                    is_terminal_accepting=False,
                )
                return AlignmentResult(
                    is_aligned=False,
                    is_inconclusive=True,
                    inconclusive_reason=f"Alignment search limit exceeded ({len(next_configs)} configurations).",
                    observed_states=observed_states_sequence,
                    coverage=self._legacy_coverage_summary(
                        covered_transitions, guard_true_outcomes, reached_milestones
                    ),
                    detailed_coverage=det_cov,
                    observation_limitations=observation_limitations,
                )

            # If all candidate configurations are ruled out:
            # THIS IS A PROVEN POINT OF DIVERGENCE!
            if not next_configs:
                candidate_states = list(
                    {cfg.current_state_id for cfg in active_configs}
                ) or [self.model.initial_state_id]
                divergence_state = candidate_states[0]

                valid_alternatives: list[str] = []
                for s in candidate_states:
                    for t in self.transitions_by_source.get(s, []):
                        if t.trigger_event not in valid_alternatives:
                            valid_alternatives.append(t.trigger_event)

                violation_type = ViolationType.INVALID_TRANSITION
                reason_msg = f"No valid transition from state(s) {candidate_states} for action '{event.tool_name}'."

                # Check entity continuity
                if "order_id" in event.arguments and active_configs:
                    bound_order = active_configs[0].variables.get("selected_order_id")
                    if (
                        bound_order is not None
                        and event.arguments["order_id"] != bound_order
                    ):
                        violation_type = ViolationType.ENTITY_MISMATCH
                        reason_msg = (
                            f"Entity continuity violation: tool called with order_id {event.arguments['order_id']}, "
                            f"but earlier step bound selected_order_id to {bound_order}."
                        )

                # Check missing effect
                for s in candidate_states:
                    for t in self.transitions_by_source.get(s, []):
                        if t.trigger_event == event.tool_name and (
                            t.expected_effects or getattr(t, "deferred_effects", None)
                        ):
                            violation_type = ViolationType.MISSING_EFFECT
                            reason_msg = f"Missing expected state effect for '{event.tool_name}' from state '{s}'."

                # Entity continuity on applications keyed by order number (e.g. NexaCart):
                # the call targeted a different order than the fixture's order.
                expected_number = fixture_ctx.get("orderNumber")
                actual_number = event.arguments.get("orderNumber")
                if (
                    expected_number is not None
                    and actual_number is not None
                    and actual_number != expected_number
                ):
                    violation_type = ViolationType.ENTITY_MISMATCH
                    reason_msg = (
                        f"Entity continuity violation: '{event.tool_name}' targeted order "
                        f"'{actual_number}', but the workflow's order is '{expected_number}'."
                    )

                first_div = FirstDivergenceDetail(
                    event_index=event.event_index,
                    event_id=event.event_id,
                    state_at_divergence=divergence_state,
                    attempted_event=event.tool_name,
                    reason=reason_msg,
                    violation_type=violation_type,
                    expected_alternatives=valid_alternatives,
                    evidence_excerpt={
                        "arguments": event.arguments,
                        "observable_result": event.observable_result,
                        "state_diff": obs.state_diff if obs else {},
                    },
                )

                violation = ViolationDetail(
                    violation_type=violation_type,
                    event_index=event.event_index,
                    event_id=event.event_id,
                    source_state=divergence_state,
                    rule_reference=f"TRANSITION_{event.tool_name}",
                    message=reason_msg,
                    expected=valid_alternatives,
                    observed=event.tool_name,
                )

                uncertainty_note = None
                if evidence_gap_reasons:
                    uncertainty_note = (
                        f"Evidence contains gaps ({'; '.join(evidence_gap_reasons)}). "
                        f"Violation at event {event.event_index} ('{event.tool_name}') is independently proven, "
                        "but earlier unobserved divergence may exist."
                    )

                det_cov = coverage_engine.compute_coverage(
                    covered_transitions=covered_transitions,
                    guard_true_outcomes=guard_true_outcomes,
                    guard_false_outcomes=guard_false_outcomes,
                    guard_unknown_observations=guard_unknown_observations,
                    satisfied_effects=satisfied_effects,
                    violated_effects=violated_effects,
                    unknown_effects=unknown_effects,
                    completed_path_history=active_configs[0].path_history
                    if active_configs
                    else [],
                    supporting_evidence=supporting_evidence,
                    is_terminal_accepting=False,
                )

                return AlignmentResult(
                    is_aligned=False,
                    violations=[violation],
                    first_divergence=first_div,
                    divergence_localisation_uncertainty=uncertainty_note,
                    observed_states=observed_states_sequence,
                    coverage=self._legacy_coverage_summary(
                        covered_transitions, guard_true_outcomes, reached_milestones
                    ),
                    detailed_coverage=det_cov,
                    observation_limitations=observation_limitations,
                )

            active_configs = next_configs
            observed_states_sequence.append(active_configs[0].current_state_id)

        # All events processed. Validate terminal configurations against task outcome
        last_obs = (
            trace.state_observations_by_index.get(trace.ordered_events[-1].event_index)
            if trace.ordered_events
            else None
        )
        final_state_snapshot = last_obs.after_state if last_obs else {}

        # 1. Protected application state verification
        first_obs = (
            trace.state_observations_by_index.get(trace.ordered_events[0].event_index)
            if trace.ordered_events
            else None
        )
        initial_state_snapshot = first_obs.before_state if first_obs else {}

        for pf in self.model.protected_fields:
            init_val = _snapshot_value(initial_state_snapshot, pf.field_path)
            final_val = _snapshot_value(final_state_snapshot, pf.field_path)
            if init_val is not None and final_val != init_val:
                violation = ViolationDetail(
                    violation_type=ViolationType.PROTECTED_FIELD_MUTATED,
                    rule_reference="PROTECTED_FIELD_INVARIANT",
                    message=f"Protected field '{pf.field_path}' was unauthorizedly mutated from '{init_val}' to '{final_val}'.",
                    expected=init_val,
                    observed=final_val,
                )
                det_cov = coverage_engine.compute_coverage(
                    covered_transitions=covered_transitions,
                    guard_true_outcomes=guard_true_outcomes,
                    guard_false_outcomes=guard_false_outcomes,
                    guard_unknown_observations=guard_unknown_observations,
                    satisfied_effects=satisfied_effects,
                    violated_effects=violated_effects,
                    unknown_effects=unknown_effects,
                    completed_path_history=active_configs[0].path_history
                    if active_configs
                    else [],
                    supporting_evidence=supporting_evidence,
                    is_terminal_accepting=False,
                )
                return AlignmentResult(
                    is_aligned=False,
                    violations=[violation],
                    observed_states=observed_states_sequence,
                    coverage=self._legacy_coverage_summary(
                        covered_transitions, guard_true_outcomes, reached_milestones
                    ),
                    detailed_coverage=det_cov,
                    observation_limitations=observation_limitations,
                )

        # 2. Check terminal state and outcome predicates
        is_negative_task = (
            test_def.expected_outcome == ExpectedOutcomeType.EXPECTED_REJECTION_PASS
            or test_def.category.value == "negative"
        )

        accepting_configs = []
        for cfg in active_configs:
            # Check any remaining unfulfilled pending effects
            if cfg.pending_effects:
                continue

            if is_negative_task:
                if cfg.current_state_id in self.model.rejection_state_ids:
                    accepting_configs.append(cfg)
            else:
                if cfg.current_state_id in self.model.accepting_state_ids:
                    target_oid = cfg.variables.get("selected_order_id")
                    target_expected = cfg.variables.get("target_latest_order_id")
                    if target_expected is not None:
                        if target_oid == target_expected:
                            is_refunded = (
                                final_state_snapshot.get("payment_status") == "REFUNDED"
                                or final_state_snapshot.get(
                                    f"order_{target_oid}_payment_status"
                                )
                                == "REFUNDED"
                            )
                            if is_refunded:
                                accepting_configs.append(cfg)
                    else:
                        # Check declared terminal outcome predicates if present
                        matching_outcomes = [
                            o
                            for o in self.model.final_outcomes
                            if o.terminal_state_id == cfg.current_state_id
                        ]
                        outcome_ok = True
                        if matching_outcomes and matching_outcomes[0].predicate:
                            out_ctx = EvaluationContext(
                                variables=cfg.variables,
                                fixture=fixture_ctx,
                                before=final_state_snapshot,
                                after=final_state_snapshot,
                            )
                            try:
                                res = evaluate_predicate(
                                    matching_outcomes[0].predicate, out_ctx
                                )
                                if res != TriState.TRUE:
                                    outcome_ok = False
                            except Exception:  # noqa: BLE001
                                outcome_ok = False
                        elif "payment_status" in final_state_snapshot:
                            if final_state_snapshot.get("payment_status") != "REFUNDED":
                                outcome_ok = False

                        if outcome_ok:
                            accepting_configs.append(cfg)

        final_path_history = (
            accepting_configs[0].path_history
            if accepting_configs
            else (active_configs[0].path_history if active_configs else [])
        )

        # If evidence had gaps and trace stopped without accepting configuration
        if not accepting_configs:
            final_state = (
                active_configs[0].current_state_id if active_configs else "UNKNOWN"
            )

            # If evidence was truncated or missing snapshots, return INCONCLUSIVE
            # (No violation was independently proven, but evidence is insufficient)
            if evidence_gap_reasons:
                det_cov = coverage_engine.compute_coverage(
                    covered_transitions=covered_transitions,
                    guard_true_outcomes=guard_true_outcomes,
                    guard_false_outcomes=guard_false_outcomes,
                    guard_unknown_observations=guard_unknown_observations,
                    satisfied_effects=satisfied_effects,
                    violated_effects=violated_effects,
                    unknown_effects=unknown_effects,
                    completed_path_history=final_path_history,
                    supporting_evidence=supporting_evidence,
                    is_terminal_accepting=False,
                )
                return AlignmentResult(
                    is_aligned=False,
                    is_inconclusive=True,
                    inconclusive_reason=(
                        f"Evidence incomplete ({'; '.join(evidence_gap_reasons)}). "
                        f"Trace ended at non-accepting state '{final_state}' without confirmed termination."
                    ),
                    observed_states=observed_states_sequence,
                    coverage=self._legacy_coverage_summary(
                        covered_transitions, guard_true_outcomes, reached_milestones
                    ),
                    detailed_coverage=det_cov,
                    observation_limitations=observation_limitations,
                )

            # If evidence was complete and honest: definite FAIL
            if (
                final_state not in self.model.accepting_state_ids
                and final_state not in self.model.rejection_state_ids
            ):
                viol_type = ViolationType.PREMATURE_TERMINATION
                msg = f"Workflow halted prematurely at non-terminal state '{final_state}'."
            else:
                viol_type = ViolationType.OUTCOME_MISMATCH
                msg = (
                    f"Final state outcome not satisfied for task '{test_def.task}'. "
                    f"Terminated at state '{final_state}' without meeting accepting outcome obligations."
                )

            violation = ViolationDetail(
                violation_type=viol_type,
                source_state=final_state,
                rule_reference="TERMINAL_OUTCOME_SPECIFICATION",
                message=msg,
                expected=(
                    self.model.rejection_state_ids
                    if is_negative_task
                    else self.model.accepting_state_ids
                ),
                observed=final_state,
            )

            det_cov = coverage_engine.compute_coverage(
                covered_transitions=covered_transitions,
                guard_true_outcomes=guard_true_outcomes,
                guard_false_outcomes=guard_false_outcomes,
                guard_unknown_observations=guard_unknown_observations,
                satisfied_effects=satisfied_effects,
                violated_effects=violated_effects,
                unknown_effects=unknown_effects,
                completed_path_history=final_path_history,
                supporting_evidence=supporting_evidence,
                is_terminal_accepting=False,
            )

            return AlignmentResult(
                is_aligned=False,
                violations=[violation],
                observed_states=observed_states_sequence,
                coverage=self._legacy_coverage_summary(
                    covered_transitions, guard_true_outcomes, reached_milestones
                ),
                detailed_coverage=det_cov,
                observation_limitations=observation_limitations,
            )

        # If accepting configurations reached, but evidence had audit anomalies or missing snapshots:
        if evidence_gap_reasons:
            det_cov = coverage_engine.compute_coverage(
                covered_transitions=covered_transitions,
                guard_true_outcomes=guard_true_outcomes,
                guard_false_outcomes=guard_false_outcomes,
                guard_unknown_observations=guard_unknown_observations,
                satisfied_effects=satisfied_effects,
                violated_effects=violated_effects,
                unknown_effects=unknown_effects,
                completed_path_history=final_path_history,
                supporting_evidence=supporting_evidence,
                is_terminal_accepting=False,
            )
            return AlignmentResult(
                is_aligned=False,
                is_inconclusive=True,
                inconclusive_reason=(
                    f"Evidence incomplete ({'; '.join(evidence_gap_reasons)}). "
                    "Cannot definitively establish complete conformance."
                ),
                observed_states=observed_states_sequence,
                coverage=self._legacy_coverage_summary(
                    covered_transitions, guard_true_outcomes, reached_milestones
                ),
                detailed_coverage=det_cov,
                observation_limitations=observation_limitations,
            )

        # Definitive Conformance Verified!
        det_cov = coverage_engine.compute_coverage(
            covered_transitions=covered_transitions,
            guard_true_outcomes=guard_true_outcomes,
            guard_false_outcomes=guard_false_outcomes,
            guard_unknown_observations=guard_unknown_observations,
            satisfied_effects=satisfied_effects,
            violated_effects=violated_effects,
            unknown_effects=unknown_effects,
            completed_path_history=final_path_history,
            supporting_evidence=supporting_evidence,
            is_terminal_accepting=not is_negative_task,
            is_terminal_rejection=is_negative_task,
        )

        return AlignmentResult(
            is_aligned=True,
            terminal_configurations=accepting_configs,
            violations=[],
            first_divergence=None,
            observed_states=observed_states_sequence,
            coverage=self._legacy_coverage_summary(
                covered_transitions, guard_true_outcomes, reached_milestones
            ),
            detailed_coverage=det_cov,
            observation_limitations=observation_limitations,
        )

    def _legacy_coverage_summary(
        self,
        covered_transitions: set[str],
        guard_true_outcomes: set[str],
        reached_milestones: set[str],
    ) -> WorkflowCoverageSummary:
        """Helper returning legacy WorkflowCoverageSummary for backwards compatibility."""
        total_guards = sum(1 for t in self.model.transitions if t.guard)
        return WorkflowCoverageSummary(
            transitions_total=len(self.model.transitions),
            transitions_covered=len(covered_transitions),
            transition_coverage_ratio=round(
                len(covered_transitions) / max(1, len(self.model.transitions)), 2
            ),
            guards_total=total_guards,
            guards_covered=len(guard_true_outcomes),
            guard_coverage_ratio=round(
                len(guard_true_outcomes) / max(1, total_guards), 2
            ),
            milestones_total=len(self.model.milestones),
            milestones_reached=len(reached_milestones),
            milestone_coverage_ratio=round(
                len(reached_milestones) / max(1, len(self.model.milestones)), 2
            ),
        )
