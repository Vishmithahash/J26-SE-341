"""Coverage-guided test generator for validated EFSM workflow models.

Generates normal, alternative, and expected-rejection paths using bounded
state-space exploration with variable binding propagation and 3-valued Kleene logic.
"""

import copy
import random
from collections import deque
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    TransitionDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExecutionMode,
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    GenerateTestSuiteRequest,
    TestCategory,
    TestReadinessStatus,
    TestSuiteDiagnostics,
)
from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
    evaluate_predicate,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonPredicate,
    FieldRef,
    ScopeEnum,
)
from app.components.c2_state_aware_workflow.predicates.tristate import TriState


class CoverageGuidedGenerator:
    """Performs coverage-guided traversal over an approved EFSM reference model.

    Tracks:
    - Current state and transition history
    - Variable bindings and fixture context
    - Guard feasibility using explicit TriState evaluation (TRUE / FALSE / UNKNOWN)
    - Loop visits and search depth bounds
    """

    def __init__(self, config: GenerateTestSuiteRequest | None = None):
        self.config = config or GenerateTestSuiteRequest(
            model_id="default", version="1.0.0"
        )
        self.rng = random.Random(self.config.seed)

    def generate(
        self,
        model: EFSMModelDefinition,
        suite_id: str,
        fixture_data: dict[str, Any] | None = None,
    ) -> tuple[list[GeneratedTestDefinition], TestSuiteDiagnostics]:
        """Generate test cases covering valid, alternative, and negative rejection paths."""
        fixture_context = fixture_data or {}
        fixture_ref = (
            self.config.fixture_ref
            or (fixture_context.get("fixture_id") if fixture_context else None)
            or "fixture_default"
        )

        all_transitions_map: dict[str, TransitionDefinition] = {
            t.id: t for t in model.transitions
        }
        all_model_transition_ids = set(all_transitions_map.keys())
        covered_transitions: set[str] = set()
        covered_guards: set[str] = set()

        cases: list[GeneratedTestDefinition] = []
        seen_case_signatures: set[tuple[Any, ...]] = set()

        paths_explored = 0
        depth_limit_reached = False
        cases_deduplicated_count = 0
        infeasible_targets_count = 0
        unresolved_constraints: list[str] = []
        generation_limits_hit: list[str] = []

        # Find terminal outcomes mapping for custom task prompts
        outcome_task_map: dict[str, str] = {}
        for outcome in model.final_outcomes:
            if outcome.task_prompt:
                outcome_task_map[outcome.terminal_state_id] = outcome.task_prompt

        accepting_ids = set(model.accepting_state_ids)
        rejection_ids = set(model.rejection_state_ids)
        target_terminal_ids = set(accepting_ids)
        if self.config.include_negative_rejections:
            target_terminal_ids.update(rejection_ids)

        # BFS queue elements:
        # (current_state_id, path_states, path_transition_ids, variables, input_params, assertions)
        initial_vars: dict[str, Any] = {}
        for var_decl in model.variables:
            if var_decl.initial_value is not None:
                initial_vars[var_decl.name] = copy.deepcopy(var_decl.initial_value)

        queue: deque[
            tuple[
                str,
                list[str],
                list[str],
                dict[str, Any],
                dict[str, Any],
                list[dict[str, Any]],
            ]
        ] = deque(
            [
                (
                    model.initial_state_id,
                    [model.initial_state_id],
                    [],
                    initial_vars,
                    {},
                    [],
                )
            ]
        )

        while queue and len(cases) < self.config.case_budget:
            curr_state, path_states, path_trans, curr_vars, curr_inputs, assertions = (
                queue.popleft()
            )
            paths_explored += 1

            # Check if current state is terminal
            if curr_state in target_terminal_ids and len(path_trans) > 0:
                is_rejection = curr_state in rejection_ids

                # Determine task prompt
                # Separate latest-paid-order from unpaid-order rejection
                if curr_state in outcome_task_map:
                    task = outcome_task_map[curr_state]
                elif is_rejection:
                    task = f"Reject ineligible request for {model.name}."
                else:
                    task = getattr(model, "task", None) or f"Execute {model.name}."

                # Determine category
                if is_rejection:
                    category = TestCategory.NEGATIVE
                    expected_outcome = ExpectedOutcomeType.EXPECTED_REJECTION_PASS
                else:
                    # Alternative vs Valid
                    # If visited an inspection / alternative intermediate state
                    is_alt = any("INSPECT" in s or "ALT" in s for s in path_states)
                    category = (
                        TestCategory.ALTERNATIVE if is_alt else TestCategory.VALID
                    )
                    expected_outcome = ExpectedOutcomeType.PASS

                # Skip alternatives if not requested
                if (
                    category == TestCategory.ALTERNATIVE
                    and not self.config.include_alternatives
                ):
                    continue

                # Signature for deduplication
                def _make_hashable(v: Any) -> Any:
                    if isinstance(v, dict):
                        return tuple(
                            sorted((k, _make_hashable(val)) for k, val in v.items())
                        )
                    if isinstance(v, (list, tuple)):
                        return tuple(_make_hashable(val) for val in v)
                    return v

                signature = (
                    tuple(path_trans),
                    _make_hashable(curr_inputs),
                    category.value,
                )
                if signature in seen_case_signatures:
                    cases_deduplicated_count += 1
                    continue
                seen_case_signatures.add(signature)

                test_id = f"TC-{model.model_id}-{category.value[:3].upper()}-{len(cases) + 1:03d}"
                case_def = GeneratedTestDefinition(
                    schema_version=model.schema_version,
                    test_id=test_id,
                    project_id=model.project_id,
                    suite_id=suite_id,
                    pinned_model_id=model.model_id,
                    pinned_model_version=model.version,
                    model_content_hash="",  # Populated by service with pinned hash
                    generator_version=self.config.generator_version,
                    category=category,
                    execution_mode=ExecutionMode.LIVE_AGENT,
                    task=task,
                    permitted_context={
                        "task": task,
                        "fixture_ref": fixture_ref,
                        "declared_tools": [m.tool_name for m in model.event_mappings],
                    },
                    fixture_ref=fixture_ref,
                    fixture_version="1.0.0",
                    seed=self.config.seed,
                    input_parameters=copy.deepcopy(curr_inputs),
                    private_reference_paths=[list(path_states)],
                    private_reference_transitions=[list(path_trans)],
                    private_reference_assertions=copy.deepcopy(assertions),
                    expected_outcome=expected_outcome,
                    planned_coverage_targets=list(path_trans),
                    readiness=TestReadinessStatus.TEST_READY,
                    readiness_reasons=[],
                )
                cases.append(case_def)
                for tid in path_trans:
                    covered_transitions.add(tid)

                # Do not expand terminal states further
                continue

            # Bounded exploration checks
            if len(path_states) >= self.config.max_depth:
                depth_limit_reached = True
                limit_msg = f"Path traversal reached max_depth ({self.config.max_depth}) at state '{curr_state}'"
                if limit_msg not in generation_limits_hit:
                    generation_limits_hit.append(limit_msg)
                continue

            # Find outgoing transitions
            out_transitions = [
                t for t in model.transitions if t.source_state == curr_state
            ]

            # Coverage-guided ordering: prioritize uncovered transitions
            def _sort_key(t: TransitionDefinition):
                is_uncovered = 0 if t.id not in covered_transitions else 1
                return (is_uncovered, t.id)

            sorted_out = sorted(out_transitions, key=_sort_key)

            for trans in sorted_out:
                # Loop visit bounding: check how many times target_state appeared in current path
                state_visits = path_states.count(trans.target_state)
                if state_visits > self.config.max_loop_visits:
                    continue

                # Feasible input domain construction for transition
                feasible_inputs, guard_sat = self._resolve_transition_inputs(
                    trans=trans,
                    current_vars=curr_vars,
                    fixture=fixture_context,
                    model=model,
                )

                if not guard_sat:
                    # Guard could not be satisfied with available domains
                    infeasible_targets_count += 1
                    continue

                # Apply transition actions to propagate variables
                next_vars = copy.deepcopy(curr_vars)
                step_context = EvaluationContext(
                    event={"arguments": feasible_inputs},
                    variables=next_vars,
                    fixture=fixture_context,
                )
                for action in trans.actions:
                    step_context.apply_update(action)

                # Record expected effect assertions
                next_assertions = copy.deepcopy(assertions)
                for eff in trans.expected_effects:
                    eff_dict = eff.model_dump(mode="json")
                    eff_dict["transition_id"] = trans.id
                    next_assertions.append(eff_dict)

                next_inputs = copy.deepcopy(curr_inputs)
                next_inputs[trans.id] = feasible_inputs

                if trans.guard:
                    covered_guards.add(trans.id)

                queue.append(
                    (
                        trans.target_state,
                        path_states + [trans.target_state],
                        path_trans + [trans.id],
                        next_vars,
                        next_inputs,
                        next_assertions,
                    )
                )

        # Build diagnostics
        total_transitions_count = len(all_model_transition_ids)
        planned_cov_pct = (
            (len(covered_transitions) / total_transitions_count * 100.0)
            if total_transitions_count > 0
            else 100.0
        )

        category_counts: dict[str, int] = {}
        readiness_breakdown = {
            TestReadinessStatus.TEST_READY.value: 0,
            TestReadinessStatus.TEST_NOT_READY.value: 0,
        }
        for c in cases:
            category_counts[c.category.value] = (
                category_counts.get(c.category.value, 0) + 1
            )
            readiness_breakdown[c.readiness.value] = (
                readiness_breakdown.get(c.readiness.value, 0) + 1
            )

        diagnostics = TestSuiteDiagnostics(
            generator_version=self.config.generator_version,
            seed=self.config.seed,
            paths_explored=paths_explored,
            depth_limit_reached=depth_limit_reached,
            cases_generated_count=len(cases),
            cases_deduplicated_count=cases_deduplicated_count,
            infeasible_targets_count=infeasible_targets_count,
            unresolved_constraints=unresolved_constraints,
            generation_limits_hit=generation_limits_hit,
            readiness_breakdown=readiness_breakdown,
            category_counts=category_counts,
            planned_transition_coverage={
                "total_transitions": total_transitions_count,
                "covered_transitions_count": len(covered_transitions),
                "covered_transition_ids": sorted(covered_transitions),
                "coverage_percentage": round(planned_cov_pct, 2),
            },
            planned_guard_coverage={
                "total_guards": sum(1 for t in model.transitions if t.guard),
                "covered_guards_count": len(covered_guards),
                "covered_guard_transition_ids": sorted(covered_guards),
            },
        )

        return cases, diagnostics

    def _resolve_transition_inputs(
        self,
        trans: TransitionDefinition,
        current_vars: dict[str, Any],
        fixture: dict[str, Any],
        model: EFSMModelDefinition,
    ) -> tuple[dict[str, Any], bool]:
        """Construct candidate tool arguments from finite domains and evaluate guard with TriState logic."""
        if not trans.guard:
            return {}, True

        # Candidate argument extraction:
        # If guard checks event.arguments.<key> == <val/ref>, extract key and target value
        candidate_args: dict[str, Any] = {}

        def _as_field_ref(val: Any) -> FieldRef | None:
            if isinstance(val, FieldRef):
                return val
            if isinstance(val, dict) and "scope" in val and "path" in val:
                try:
                    return FieldRef(**val)
                except Exception:  # noqa: BLE001
                    return None
            return None

        if isinstance(trans.guard, ComparisonPredicate):
            arg_key = None
            target_val = None

            left_ref = _as_field_ref(trans.guard.left)
            right_ref = _as_field_ref(trans.guard.right)

            if left_ref is not None and left_ref.scope == ScopeEnum.EVENT:
                parts = left_ref.path.split(".")
                arg_key = parts[-1]
                if right_ref is not None:
                    ctx = EvaluationContext(variables=current_vars, fixture=fixture)
                    resolved = ctx.resolve(right_ref)
                    if resolved is not None and resolved is not ScopeEnum.EVENT:
                        target_val = resolved
                else:
                    target_val = trans.guard.right

            elif right_ref is not None and right_ref.scope == ScopeEnum.EVENT:
                parts = right_ref.path.split(".")
                arg_key = parts[-1]
                if left_ref is not None:
                    ctx = EvaluationContext(variables=current_vars, fixture=fixture)
                    resolved = ctx.resolve(left_ref)
                    if resolved is not None and resolved is not ScopeEnum.EVENT:
                        target_val = resolved
                else:
                    target_val = trans.guard.left

            if arg_key and target_val is not None:
                candidate_args[arg_key] = target_val

        # If guard is more complex or candidate_args empty, look up variable domains
        if not candidate_args:
            for v in model.variables:
                if v.domain:
                    # Pick first domain value or seeded choice
                    candidate_args[v.name] = v.domain[0]

        # Evaluate guard using TriState
        test_ctx = EvaluationContext(
            event={"arguments": candidate_args},
            variables=current_vars,
            fixture=fixture,
        )

        try:
            tristate_result = evaluate_predicate(trans.guard, test_ctx)
            # NEVER use direct boolean coercion bool(tristate_result)
            if tristate_result == TriState.TRUE:
                return candidate_args, True
            else:
                return candidate_args, False
        except Exception:  # noqa: BLE001
            return candidate_args, False
