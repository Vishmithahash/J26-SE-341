"""Trace-to-EFSM alignment engine with non-deterministic branching and failure localisation.

Tracks all currently feasible configurations simultaneously across model states,
runtime variable bindings, guard outcomes, and effect obligations.
Localises the earliest proven point of divergence where all candidate model paths
are ruled out by observable evidence.
"""

import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
from app.components.c2_state_aware_workflow.evaluator.normalizer import NormalizedTrace
from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
    evaluate_predicate,
)
from app.components.c2_state_aware_workflow.predicates.tristate import TriState


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
    observed_states: list[str] = Field(default_factory=list)
    coverage: WorkflowCoverageSummary = Field(default_factory=WorkflowCoverageSummary)


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
        # Check trace audit anomalies first
        if trace.has_audit_anomalies:
            return AlignmentResult(
                is_aligned=False,
                is_inconclusive=True,
                inconclusive_reason=f"Evidence audit anomalies detected: {'; '.join(trace.diagnostics)}",
            )

        # Check for truncated trace without confirmed agent termination
        if (
            trace.completeness.is_truncated
            or not trace.completeness.confirmed_agent_termination
        ):
            return AlignmentResult(
                is_aligned=False,
                is_inconclusive=True,
                inconclusive_reason=(
                    "Evidence collection stopped or was truncated without confirmed agent termination marker. "
                    "Cannot definitively determine conformance."
                ),
            )

        fixture_ctx = fixture_data or test_def.permitted_context.get("fixture", {})

        # Initialise variables from model declarations
        initial_vars: dict[str, Any] = {}
        for v in self.model.variables:
            if v.initial_value is not None:
                initial_vars[v.name] = copy.deepcopy(v.initial_value)

        # Dynamic entity binding from fixture context if provided (supports arbitrary customer/order IDs)
        if "customer_id" in fixture_ctx:
            initial_vars["requesting_customer_id"] = fixture_ctx["customer_id"]
        if "orders" in fixture_ctx and isinstance(fixture_ctx["orders"], (list, dict)):
            raw_orders = fixture_ctx["orders"]
            orders_list = (
                list(raw_orders.values())
                if isinstance(raw_orders, dict)
                else list(raw_orders)
            )
            paid_orders = [
                o
                for o in orders_list
                if o.get("payment_status") == "PAID" or o.get("status") == "PAID"
            ]
            if paid_orders:
                paid_orders.sort(
                    key=lambda x: str(x.get("ordered_at", "")), reverse=True
                )
                initial_vars["target_latest_order_id"] = paid_orders[0].get(
                    "order_id"
                ) or paid_orders[0].get("id")

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

        # Tracking coverage
        covered_transitions: set[str] = set()
        covered_guards: set[str] = set()
        reached_milestones: set[str] = set()
        observed_states_sequence: list[str] = [self.model.initial_state_id]

        # Process events step by step
        for i, event in enumerate(trace.ordered_events):
            next_configs: list[FeasibleConfiguration] = []
            obs = trace.state_observations_by_index.get(event.event_index)

            # Missing mandatory state observation produces INCONCLUSIVE
            if obs is None:
                return AlignmentResult(
                    is_aligned=False,
                    is_inconclusive=True,
                    inconclusive_reason=(
                        f"Missing mandatory state snapshot for event index {event.event_index} ('{event.tool_name}')."
                    ),
                )

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
                    # 1. Entity Continuity Check:
                    # If variables already bind selected_order_id, verify order_id matches
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

                    guard_sat = TriState.TRUE
                    if trans.guard:
                        try:
                            guard_sat = evaluate_predicate(trans.guard, eval_ctx)
                        except Exception:  # noqa: BLE001
                            guard_sat = TriState.UNKNOWN

                    # TriState.FALSE strictly prunes candidate transition
                    if guard_sat == TriState.FALSE:
                        continue

                    if trans.guard and guard_sat == TriState.TRUE:
                        covered_guards.add(trans.id)

                    # 3. Apply transition updates to runtime variables
                    next_vars = copy.deepcopy(config.variables)
                    update_ctx = EvaluationContext(
                        event={
                            "arguments": event.arguments,
                            "result": event.observable_result,
                        },
                        variables=next_vars,
                        fixture=fixture_ctx,
                        before=obs.before_state,
                        after=obs.after_state,
                    )
                    for action in trans.actions:
                        update_ctx.apply_update(action)

                    # Dynamic entity binding: if event is select_order, bind selected_order_id
                    if (
                        event.tool_name == "select_order"
                        and "order_id" in event.arguments
                    ):
                        next_vars["selected_order_id"] = event.arguments["order_id"]

                    # 4. Check immediate expected state effects
                    effects_ok = True
                    for eff in trans.expected_effects:
                        # Verify effect condition on after_state
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
                            if res != TriState.TRUE:
                                effects_ok = False
                                break
                        except Exception:  # noqa: BLE001
                            effects_ok = False
                            break

                    if not effects_ok:
                        continue  # State effect did not manifest in observed application state

                    # 5. Check workflow invariants
                    invariants_ok = True
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
                            pending_effects=config.pending_effects,
                        )
                    )

            # Check resource limit (branch budget)
            if len(next_configs) > self.max_configurations:
                return AlignmentResult(
                    is_aligned=False,
                    is_inconclusive=True,
                    inconclusive_reason=f"Alignment search limit exceeded ({len(next_configs)} configurations).",
                )

            # If all candidate configurations ruled out at this event index:
            # THIS IS THE FIRST PROVEN POINT OF DIVERGENCE!
            if not next_configs:
                divergence_state = (
                    active_configs[0].current_state_id
                    if active_configs
                    else self.model.initial_state_id
                )
                valid_alternatives = [
                    t.trigger_event
                    for t in self.transitions_by_source.get(divergence_state, [])
                ]

                # Classify specific violation
                violation_type = ViolationType.INVALID_TRANSITION
                reason_msg = f"No valid transition from state '{divergence_state}' for action '{event.tool_name}'."

                # Check if entity continuity was the reason
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

                # Check if missing effect on expected transition
                for t in self.transitions_by_source.get(divergence_state, []):
                    if t.trigger_event == event.tool_name and t.expected_effects:
                        violation_type = ViolationType.MISSING_EFFECT
                        reason_msg = f"Missing expected state effect for '{event.tool_name}' from state '{divergence_state}'."

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
                        "state_diff": obs.state_diff,
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

                return AlignmentResult(
                    is_aligned=False,
                    violations=[violation],
                    first_divergence=first_div,
                    observed_states=observed_states_sequence,
                    coverage=WorkflowCoverageSummary(
                        transitions_total=len(self.model.transitions),
                        transitions_covered=len(covered_transitions),
                        transition_coverage_ratio=round(
                            len(covered_transitions)
                            / max(1, len(self.model.transitions)),
                            2,
                        ),
                        guards_total=sum(1 for t in self.model.transitions if t.guard),
                        guards_covered=len(covered_guards),
                        guard_coverage_ratio=round(
                            len(covered_guards)
                            / max(1, sum(1 for t in self.model.transitions if t.guard)),
                            2,
                        ),
                        milestones_total=len(self.model.milestones),
                        milestones_reached=len(reached_milestones),
                        milestone_coverage_ratio=round(
                            len(reached_milestones)
                            / max(1, len(self.model.milestones)),
                            2,
                        ),
                    ),
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

        # 1. Protected application state verification:
        # Protected fields must remain unchanged
        first_obs = (
            trace.state_observations_by_index.get(trace.ordered_events[0].event_index)
            if trace.ordered_events
            else None
        )
        initial_state_snapshot = first_obs.before_state if first_obs else {}

        for pf in self.model.protected_fields:
            init_val = initial_state_snapshot.get(pf.field_path)
            final_val = final_state_snapshot.get(pf.field_path)
            if init_val is not None and final_val != init_val:
                violation = ViolationDetail(
                    violation_type=ViolationType.PROTECTED_FIELD_MUTATED,
                    rule_reference="PROTECTED_FIELD_INVARIANT",
                    message=f"Protected field '{pf.field_path}' was unauthorizedly mutated from '{init_val}' to '{final_val}'.",
                    expected=init_val,
                    observed=final_val,
                )
                return AlignmentResult(
                    is_aligned=False,
                    violations=[violation],
                    observed_states=observed_states_sequence,
                )

        # 2. Check terminal state and outcome predicates
        is_negative_task = (
            test_def.expected_outcome == ExpectedOutcomeType.EXPECTED_REJECTION_PASS
            or test_def.category.value == "negative"
        )

        accepting_configs = []
        for cfg in active_configs:
            if is_negative_task:
                if cfg.current_state_id in self.model.rejection_state_ids:
                    accepting_configs.append(cfg)
            else:
                if cfg.current_state_id in self.model.accepting_state_ids:
                    # For positive tasks: verify that the target entity was actually refunded
                    # Enforce task-specific outcome: rejecting unpaid order does NOT satisfy refunding latest paid order!
                    target_oid = cfg.variables.get("selected_order_id")
                    target_expected = cfg.variables.get("target_latest_order_id")
                    if target_expected is None or target_oid == target_expected:
                        # Verify payment_status in final state
                        is_refunded = (
                            final_state_snapshot.get("payment_status") == "REFUNDED"
                            or final_state_snapshot.get(
                                f"order_{target_oid}_payment_status"
                            )
                            == "REFUNDED"
                        )
                        if is_refunded:
                            accepting_configs.append(cfg)

        if not accepting_configs:
            # Terminated at a non-accepting state or unmet outcome
            final_state = (
                active_configs[0].current_state_id if active_configs else "UNKNOWN"
            )

            # Check if premature termination before final state
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
            return AlignmentResult(
                is_aligned=False,
                violations=[violation],
                observed_states=observed_states_sequence,
            )

        # Conformance verified!
        coverage_summary = WorkflowCoverageSummary(
            transitions_total=len(self.model.transitions),
            transitions_covered=len(covered_transitions),
            transition_coverage_ratio=round(
                len(covered_transitions) / max(1, len(self.model.transitions)), 2
            ),
            guards_total=sum(1 for t in self.model.transitions if t.guard),
            guards_covered=len(covered_guards),
            guard_coverage_ratio=round(
                len(covered_guards)
                / max(1, sum(1 for t in self.model.transitions if t.guard)),
                2,
            ),
            milestones_total=len(self.model.milestones),
            milestones_reached=len(reached_milestones),
            milestone_coverage_ratio=round(
                len(reached_milestones) / max(1, len(self.model.milestones)), 2
            ),
        )

        return AlignmentResult(
            is_aligned=True,
            terminal_configurations=accepting_configs,
            violations=[],
            first_divergence=None,
            observed_states=observed_states_sequence,
            coverage=coverage_summary,
        )
