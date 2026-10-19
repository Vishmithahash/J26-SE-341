"""Bounded semantic validator for EFSM workflow models."""

from collections import deque
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    LogicalOperator,
    LogicalPredicate,
    StructuredPredicate,
    VariableUpdateOp,
)


class BoundedSemanticValidator:
    """Performs bounded semantic checks over declared finite domains for EFSM models.

    Preserves legitimate alternative paths; multiple transitions sharing an event
    or state are recognized as valid branches unless explicitly contradictory.
    """

    def __init__(self, max_search_depth: int = 20):
        self.max_search_depth = max_search_depth

    def validate(
        self, model: EFSMModelDefinition
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        diagnostics: dict[str, Any] = {
            "max_search_depth": self.max_search_depth,
            "alternative_paths_identified": 0,
            "guards_checked": 0,
            "invariants_checked": len(model.invariants),
        }

        # 1. Guard Feasibility & Contradiction Check
        for trans in model.transitions:
            if trans.guard:
                diagnostics["guards_checked"] += 1
                if self._is_contradictory_predicate(trans.guard):
                    errors.append(
                        {
                            "check": "guard_feasibility",
                            "transition_id": trans.id,
                            "message": f"Transition '{trans.id}' has an infeasible (contradictory) guard condition.",
                            "severity": "CRITICAL",
                        }
                    )

        # 2. Conflicting Variable Updates on a Single Transition
        for trans in model.transitions:
            set_targets: dict[str, Any] = {}
            for action in trans.actions:
                if (
                    action.op == VariableUpdateOp.SET
                    and action.literal_value is not None
                ):
                    if action.target_var in set_targets:
                        if set_targets[action.target_var] != action.literal_value:
                            errors.append(
                                {
                                    "check": "conflicting_updates",
                                    "transition_id": trans.id,
                                    "message": (
                                        f"Transition '{trans.id}' contains conflicting updates for variable '{action.target_var}': "
                                        f"{set_targets[action.target_var]} vs {action.literal_value}"
                                    ),
                                    "severity": "CRITICAL",
                                }
                            )
                    else:
                        set_targets[action.target_var] = action.literal_value

        # 3. Protected-State Rejection Rules
        # Ensure transitions leading into rejection states do not alter protected fields
        rejection_ids = set(model.rejection_state_ids)
        protected_paths = {
            pf.field_path
            for pf in model.protected_fields
            if pf.strict_unchanged_on_rejection
        }
        for trans in model.transitions:
            if trans.target_state in rejection_ids:
                # Check actions for modifications to protected fields
                for action in trans.actions:
                    if action.target_var in protected_paths:
                        errors.append(
                            {
                                "check": "protected_state_rejection",
                                "transition_id": trans.id,
                                "message": (
                                    f"Transition '{trans.id}' leads to rejection state '{trans.target_state}' "
                                    f"but mutates protected field/variable '{action.target_var}'."
                                ),
                                "severity": "CRITICAL",
                            }
                        )
                # Check expected effects for state alterations on protected paths
                for eff in trans.expected_effects:
                    if (
                        hasattr(eff, "left")
                        and isinstance(eff.left, FieldRef)
                        and eff.left.path in protected_paths
                    ):
                        errors.append(
                            {
                                "check": "protected_state_rejection",
                                "transition_id": trans.id,
                                "message": (
                                    f"Transition '{trans.id}' leads to rejection state '{trans.target_state}' "
                                    f"but declares state modification on protected path '{eff.left.path}'."
                                ),
                                "severity": "CRITICAL",
                            }
                        )

        # 4. Feasible Accepting Reachability (Bounded Path Search)
        accepting_ids = set(model.accepting_state_ids)
        queue = deque([(model.initial_state_id, 0, [model.initial_state_id])])
        feasible_accepting_found = False
        valid_paths_found = 0
        depth_limit_hit = False

        while queue:
            curr_state, depth, path = queue.popleft()
            if curr_state in accepting_ids:
                feasible_accepting_found = True
                valid_paths_found += 1
                if valid_paths_found > 1:
                    diagnostics["alternative_paths_identified"] += 1
                # Once an accepting state is reached, do not continue extending this path
                continue

            if depth < self.max_search_depth:
                out_transitions = [
                    t for t in model.transitions if t.source_state == curr_state
                ]
                for trans in out_transitions:
                    # Skip transitions with known contradictory guards
                    if trans.guard and self._is_contradictory_predicate(trans.guard):
                        continue
                    nxt = trans.target_state
                    # Prevent cycles along the current exploration path
                    if nxt not in path:
                        queue.append((nxt, depth + 1, path + [nxt]))
            else:
                depth_limit_hit = True

        if not feasible_accepting_found:
            if depth_limit_hit:
                # Bounded limit reached without proof of infeasibility
                warnings.append(
                    {
                        "check": "bounded_search_depth_limit",
                        "message": (
                            f"Accepting state reachability unresolved within bounded search depth {self.max_search_depth}. "
                            "Treated as an unresolved check rather than proof of infeasibility or unreachability."
                        ),
                        "severity": "WARNING",
                    }
                )
                diagnostics["unresolved_checks"] = diagnostics.get(
                    "unresolved_checks", []
                ) + ["feasible_accepting_reachability_bounded_limit"]
            else:
                errors.append(
                    {
                        "check": "feasible_accepting_reachability",
                        "message": "No feasible accepting path exists from initial state (reachable state space exhausted).",
                        "severity": "CRITICAL",
                    }
                )

        # 5. Invariant / Effect Compatibility
        # Check if an expected effect on a transition directly contradicts any declared invariant
        for inv in model.invariants:
            for trans in model.transitions:
                for eff in trans.expected_effects:
                    if self._is_effect_contradicting_invariant(eff, inv.predicate):
                        errors.append(
                            {
                                "check": "invariant_effect_compatibility",
                                "transition_id": trans.id,
                                "invariant_id": inv.id,
                                "message": (
                                    f"Transition '{trans.id}' expected effect directly contradicts invariant '{inv.id}'."
                                ),
                                "severity": "CRITICAL",
                            }
                        )

        return errors, warnings, diagnostics

    def _is_contradictory_predicate(self, pred: StructuredPredicate) -> bool:
        """Detect obvious literal contradictions in AND conjunctions, e.g. x == 'A' AND x == 'B'."""
        if isinstance(pred, LogicalPredicate) and pred.op == LogicalOperator.AND:
            equality_map: dict[str, Any] = {}
            for clause in pred.clauses:
                if (
                    isinstance(clause, ComparisonPredicate)
                    and clause.op == ComparisonOperator.EQUALS
                ):
                    if isinstance(clause.left, FieldRef) and not isinstance(
                        clause.right, FieldRef
                    ):
                        key = clause.left.full_path
                        val = clause.right
                        if key in equality_map and equality_map[key] != val:
                            return True
                        equality_map[key] = val
                    elif isinstance(clause.right, FieldRef) and not isinstance(
                        clause.left, FieldRef
                    ):
                        key = clause.right.full_path
                        val = clause.left
                        if key in equality_map and equality_map[key] != val:
                            return True
                        equality_map[key] = val
                elif isinstance(
                    clause, LogicalPredicate
                ) and self._is_contradictory_predicate(clause):
                    return True
        return False

    def _is_effect_contradicting_invariant(
        self,
        effect: StructuredPredicate,
        invariant: StructuredPredicate,
    ) -> bool:
        """Check if an effect setting field X == V contradicts an invariant X != V or NOT (X == V)."""
        if (
            isinstance(effect, ComparisonPredicate)
            and effect.op == ComparisonOperator.EQUALS
            and isinstance(effect.left, FieldRef)
            and not isinstance(effect.right, FieldRef)
        ):
            path = effect.left.path
            val = effect.right
            # Invariant: left != right
            if (
                isinstance(invariant, ComparisonPredicate)
                and invariant.op == ComparisonOperator.NOT_EQUALS
                and isinstance(invariant.left, FieldRef)
                and invariant.left.path == path
                and invariant.right == val
            ):
                return True
            # Invariant: NOT (left == right)
            if (
                isinstance(invariant, LogicalPredicate)
                and invariant.op == LogicalOperator.NOT
                and len(invariant.clauses) == 1
                and isinstance(invariant.clauses[0], ComparisonPredicate)
                and invariant.clauses[0].op == ComparisonOperator.EQUALS
                and isinstance(invariant.clauses[0].left, FieldRef)
                and invariant.clauses[0].left.path == path
                and invariant.clauses[0].right == val
            ):
                return True
        return False
