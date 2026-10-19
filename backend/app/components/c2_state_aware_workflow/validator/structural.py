"""Structural validator for EFSM workflow models."""

from collections import deque
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    StateType,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    FieldRef,
    ScopeEnum,
    StructuredPredicate,
)


class StructuralValidator:
    """Performs static graph and structural integrity checks on an EFSM definition."""

    def validate(
        self, model: EFSMModelDefinition
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # 1. Duplicate State IDs
        state_ids: set[str] = set()
        duplicate_states: set[str] = set()
        for state in model.states:
            if state.id in state_ids:
                duplicate_states.add(state.id)
            state_ids.add(state.id)

        if duplicate_states:
            errors.append(
                {
                    "check": "unique_state_ids",
                    "message": f"Duplicate state IDs found: {sorted(duplicate_states)}",
                    "severity": "CRITICAL",
                }
            )

        # 2. Duplicate Transition IDs
        trans_ids: set[str] = set()
        duplicate_trans: set[str] = set()
        for trans in model.transitions:
            if trans.id in trans_ids:
                duplicate_trans.add(trans.id)
            trans_ids.add(trans.id)

        if duplicate_trans:
            errors.append(
                {
                    "check": "unique_transition_ids",
                    "message": f"Duplicate transition IDs found: {sorted(duplicate_trans)}",
                    "severity": "CRITICAL",
                }
            )

        # 3. Initial State Validity
        if model.initial_state_id not in state_ids:
            errors.append(
                {
                    "check": "initial_state_exists",
                    "message": f"Initial state '{model.initial_state_id}' is not in declared states.",
                    "severity": "CRITICAL",
                }
            )
        else:
            initial_state_def = next(
                s for s in model.states if s.id == model.initial_state_id
            )
            if initial_state_def.type != StateType.INITIAL:
                errors.append(
                    {
                        "check": "initial_state_type",
                        "message": f"Initial state '{model.initial_state_id}' must have type 'initial', got '{initial_state_def.type}'.",
                        "severity": "CRITICAL",
                    }
                )

        # 4. Terminal States Validity
        declared_terminal_ids = {
            s.id
            for s in model.states
            if s.type in (StateType.TERMINAL_ACCEPTING, StateType.TERMINAL_REJECTION)
        }
        for acc_id in model.accepting_state_ids:
            if acc_id not in state_ids:
                errors.append(
                    {
                        "check": "accepting_state_exists",
                        "message": f"Accepting state '{acc_id}' is not in declared states.",
                        "severity": "CRITICAL",
                    }
                )

        for rej_id in model.rejection_state_ids:
            if rej_id not in state_ids:
                errors.append(
                    {
                        "check": "rejection_state_exists",
                        "message": f"Rejection state '{rej_id}' is not in declared states.",
                        "severity": "CRITICAL",
                    }
                )

        # 5. Dangling Transitions
        for trans in model.transitions:
            if trans.source_state not in state_ids:
                errors.append(
                    {
                        "check": "valid_source_state",
                        "message": f"Transition '{trans.id}' has undeclared source state '{trans.source_state}'.",
                        "severity": "CRITICAL",
                    }
                )
            if trans.target_state not in state_ids:
                errors.append(
                    {
                        "check": "valid_target_state",
                        "message": f"Transition '{trans.id}' has undeclared target state '{trans.target_state}'.",
                        "severity": "CRITICAL",
                    }
                )

        # 6. Graph Reachability (from initial state)
        if model.initial_state_id in state_ids:
            adjacency: dict[str, list[str]] = {sid: [] for sid in state_ids}
            for trans in model.transitions:
                if trans.source_state in adjacency and trans.target_state in state_ids:
                    adjacency[trans.source_state].append(trans.target_state)

            reachable: set[str] = set()
            queue = deque([model.initial_state_id])
            reachable.add(model.initial_state_id)

            while queue:
                curr = queue.popleft()
                for nxt in adjacency.get(curr, []):
                    if nxt not in reachable:
                        reachable.add(nxt)
                        queue.append(nxt)

            unreachable = state_ids - reachable
            if unreachable:
                errors.append(
                    {
                        "check": "unreachable_states",
                        "message": f"Unreachable states detected from initial state: {sorted(unreachable)}",
                        "severity": "CRITICAL",
                    }
                )

        # 7. Non-terminal Dead Ends (states with no outgoing transitions that are not marked terminal)
        outgoing_counts: dict[str, int] = {sid: 0 for sid in state_ids}
        for trans in model.transitions:
            if trans.source_state in outgoing_counts:
                outgoing_counts[trans.source_state] += 1

        for state in model.states:
            if (
                state.type
                not in (StateType.TERMINAL_ACCEPTING, StateType.TERMINAL_REJECTION)
                and outgoing_counts.get(state.id, 0) == 0
            ):
                errors.append(
                    {
                        "check": "nonterminal_dead_end",
                        "message": f"Non-terminal state '{state.id}' has no outgoing transitions (dead end).",
                        "severity": "CRITICAL",
                    }
                )

        # 8. Declared Terminal States must have associated Final Outcomes
        outcome_terminals = {o.terminal_state_id for o in model.final_outcomes}
        for term_id in declared_terminal_ids:
            if term_id not in outcome_terminals:
                warnings.append(
                    {
                        "check": "outcome_coverage",
                        "message": f"Terminal state '{term_id}' does not have an explicit FinalOutcome declared.",
                        "severity": "MEDIUM",
                    }
                )

        # 9. Validate Predicate Scopes and References
        declared_vars = {v.name for v in model.variables}
        for trans in model.transitions:
            if trans.guard:
                self._validate_predicate_refs(
                    trans.guard, declared_vars, warnings, f"Transition {trans.id} guard"
                )
            for eff in trans.expected_effects:
                self._validate_predicate_refs(
                    eff, declared_vars, warnings, f"Transition {trans.id} effect"
                )

        return errors, warnings

    def _validate_predicate_refs(
        self,
        pred: StructuredPredicate,
        declared_vars: set[str],
        warnings: list[dict[str, Any]],
        context_label: str,
    ) -> None:
        if (
            hasattr(pred, "target")
            and isinstance(pred.target, FieldRef)
            and pred.target.scope == ScopeEnum.VARS
            and pred.target.path not in declared_vars
        ):
            warnings.append(
                {
                    "check": "variable_reference",
                    "message": f"{context_label} references undeclared variable '{pred.target.path}'.",
                    "severity": "LOW",
                }
            )
        if (
            hasattr(pred, "left")
            and isinstance(pred.left, FieldRef)
            and pred.left.scope == ScopeEnum.VARS
            and pred.left.path not in declared_vars
        ):
            warnings.append(
                {
                    "check": "variable_reference",
                    "message": f"{context_label} left operand references undeclared variable '{pred.left.path}'.",
                    "severity": "LOW",
                }
            )
        if (
            hasattr(pred, "right")
            and isinstance(pred.right, FieldRef)
            and pred.right.scope == ScopeEnum.VARS
            and pred.right.path not in declared_vars
        ):
            warnings.append(
                {
                    "check": "variable_reference",
                    "message": f"{context_label} right operand references undeclared variable '{pred.right.path}'.",
                    "severity": "LOW",
                }
            )
        if hasattr(pred, "clauses"):
            for cl in pred.clauses:
                self._validate_predicate_refs(
                    cl, declared_vars, warnings, context_label
                )
