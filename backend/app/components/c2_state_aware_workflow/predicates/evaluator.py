"""Declarative predicate evaluator with three-valued Kleene logic and safe execution."""

from collections.abc import Iterable, Mapping
from typing import Any

from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    LiteralPredicate,
    LogicalOperator,
    LogicalPredicate,
    PresenceOperator,
    PresencePredicate,
    ScopeEnum,
    StructuredPredicate,
    VariableUpdate,
    VariableUpdateOp,
)
from app.components.c2_state_aware_workflow.predicates.tristate import (
    MISSING,
    TriState,
    is_missing,
)


class PredicateEvaluationError(Exception):
    """Base exception for predicate evaluation errors."""


class PredicateTypeError(PredicateEvaluationError):
    """Raised when operand types are incompatible with the chosen operator."""


class EvaluationContext:
    """Explicitly scoped context for predicate evaluation and variable updates."""

    def __init__(
        self,
        event: Mapping[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
        fixture: Mapping[str, Any] | None = None,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
    ):
        self.scopes: dict[ScopeEnum, Any] = {
            ScopeEnum.EVENT: event if event is not None else MISSING,
            ScopeEnum.VARS: variables if variables is not None else {},
            ScopeEnum.FIXTURE: fixture if fixture is not None else MISSING,
            ScopeEnum.BEFORE: before if before is not None else MISSING,
            ScopeEnum.AFTER: after if after is not None else MISSING,
        }

    def resolve(self, ref: FieldRef) -> Any:
        """Resolve a field reference against its explicit scope.

        Distinguishes missing observations (MISSING) from explicit null (None).
        """
        scope_data = self.scopes.get(ref.scope)
        if is_missing(scope_data) or scope_data is None:
            return MISSING

        if not ref.path:
            return scope_data

        parts = ref.path.split(".")
        current: Any = scope_data

        for part in parts:
            if isinstance(current, Mapping):
                if part in current:
                    current = current[part]
                else:
                    return MISSING
            elif isinstance(current, (list, tuple)):
                try:
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return MISSING
                except ValueError:
                    return MISSING
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return MISSING

        return current

    def apply_update(self, update: VariableUpdate) -> None:
        """Apply a declarative variable binding/update to the 'vars' scope."""
        vars_dict = self.scopes[ScopeEnum.VARS]
        if not isinstance(vars_dict, dict):
            vars_dict = {}
            self.scopes[ScopeEnum.VARS] = vars_dict

        if update.source_ref is not None:
            value = self.resolve(update.source_ref)
        else:
            value = update.literal_value

        if update.op == VariableUpdateOp.SET:
            vars_dict[update.target_var] = value
        elif update.op == VariableUpdateOp.DELETE:
            vars_dict.pop(update.target_var, None)
        elif update.op == VariableUpdateOp.APPEND:
            existing = vars_dict.get(update.target_var)
            if existing is None:
                vars_dict[update.target_var] = [value]
            elif isinstance(existing, list):
                existing.append(value)
            else:
                raise PredicateTypeError(
                    f"Cannot APPEND to non-list variable '{update.target_var}' (type: {type(existing).__name__})"
                )
        elif update.op == VariableUpdateOp.INCREMENT:
            existing = vars_dict.get(update.target_var, 0)
            if isinstance(existing, (int, float)) and isinstance(value, (int, float)):
                vars_dict[update.target_var] = existing + value
            else:
                raise PredicateTypeError(
                    f"Cannot INCREMENT non-numeric variable '{update.target_var}' with {value}"
                )


def _resolve_operand(val: Any, context: EvaluationContext) -> Any:
    if isinstance(val, FieldRef):
        return context.resolve(val)
    if isinstance(val, dict) and "scope" in val and "path" in val:
        return context.resolve(FieldRef(**val))
    return val


def evaluate_predicate(
    pred: StructuredPredicate | Mapping[str, Any],
    context: EvaluationContext,
) -> TriState:
    """Evaluate a structured predicate using three-valued logic.

    Returns:
        TriState.TRUE, TriState.FALSE, or TriState.UNKNOWN
    """
    if isinstance(pred, Mapping):
        pred_type = pred.get("type")
        if pred_type == "comparison":
            pred = ComparisonPredicate(**pred)
        elif pred_type == "presence":
            pred = PresencePredicate(**pred)
        elif pred_type == "logical":
            pred = LogicalPredicate(**pred)
        elif pred_type == "literal":
            pred = LiteralPredicate(**pred)
        else:
            raise PredicateEvaluationError(f"Unknown predicate type: {pred_type}")

    if isinstance(pred, LiteralPredicate):
        return TriState(pred.value)

    if isinstance(pred, PresencePredicate):
        val = context.resolve(pred.target)
        if pred.op == PresenceOperator.EXISTS:
            return TriState.FALSE if is_missing(val) else TriState.TRUE
        if pred.op == PresenceOperator.NOT_EXISTS:
            return TriState.TRUE if is_missing(val) else TriState.FALSE
        if pred.op == PresenceOperator.IS_NULL:
            if is_missing(val):
                return TriState.UNKNOWN
            return TriState.TRUE if val is None else TriState.FALSE
        if pred.op == PresenceOperator.IS_NOT_NULL:
            if is_missing(val):
                return TriState.UNKNOWN
            return TriState.FALSE if val is None else TriState.TRUE
        raise PredicateEvaluationError(f"Unsupported presence operator '{pred.op}'")

    if isinstance(pred, LogicalPredicate):
        if pred.op == LogicalOperator.NOT:
            if len(pred.clauses) != 1:
                raise PredicateEvaluationError(
                    "Logical NOT must contain exactly one clause."
                )
            return evaluate_predicate(pred.clauses[0], context).lnot()

        if pred.op == LogicalOperator.AND:
            if not pred.clauses:
                return TriState.TRUE
            result = TriState.TRUE
            for clause in pred.clauses:
                clause_res = evaluate_predicate(clause, context)
                result = result.land(clause_res)
                if result == TriState.FALSE:
                    return TriState.FALSE
            return result

        if pred.op == LogicalOperator.OR:
            if not pred.clauses:
                return TriState.FALSE
            result = TriState.FALSE
            for clause in pred.clauses:
                clause_res = evaluate_predicate(clause, context)
                result = result.lor(clause_res)
                if result == TriState.TRUE:
                    return TriState.TRUE
            return result

        raise PredicateEvaluationError(f"Unsupported logical operator '{pred.op}'")

    if isinstance(pred, ComparisonPredicate):
        left_val = _resolve_operand(pred.left, context)
        right_val = _resolve_operand(pred.right, context)

        # In three-valued logic, if any required observation is missing, the comparison is UNKNOWN
        if is_missing(left_val) or is_missing(right_val):
            return TriState.UNKNOWN

        op = pred.op
        if op == ComparisonOperator.EQUALS:
            return TriState.TRUE if left_val == right_val else TriState.FALSE
        if op == ComparisonOperator.NOT_EQUALS:
            return TriState.TRUE if left_val != right_val else TriState.FALSE

        # Strict relational and membership operators require type validation
        if op in (
            ComparisonOperator.LESS_THAN,
            ComparisonOperator.LESS_EQUAL,
            ComparisonOperator.GREATER_THAN,
            ComparisonOperator.GREATER_EQUAL,
        ):
            if left_val is None or right_val is None:
                return TriState.UNKNOWN
            if not (
                (
                    isinstance(left_val, (int, float))
                    and isinstance(right_val, (int, float))
                )
                or (isinstance(left_val, str) and isinstance(right_val, str))
            ):
                raise PredicateTypeError(
                    f"Incompatible types for comparison '{op.value}': {type(left_val).__name__} and {type(right_val).__name__}"
                )

            if op == ComparisonOperator.LESS_THAN:
                return TriState.TRUE if left_val < right_val else TriState.FALSE
            if op == ComparisonOperator.LESS_EQUAL:
                return TriState.TRUE if left_val <= right_val else TriState.FALSE
            if op == ComparisonOperator.GREATER_THAN:
                return TriState.TRUE if left_val > right_val else TriState.FALSE
            if op == ComparisonOperator.GREATER_EQUAL:
                return TriState.TRUE if left_val >= right_val else TriState.FALSE

        if op in (ComparisonOperator.IN, ComparisonOperator.NOT_IN):
            if not isinstance(right_val, Iterable):
                raise PredicateTypeError(
                    f"Right operand of 'in' must be an iterable, got {type(right_val).__name__}"
                )
            is_in = left_val in right_val
            if op == ComparisonOperator.IN:
                return TriState.TRUE if is_in else TriState.FALSE
            return TriState.FALSE if is_in else TriState.TRUE

        if op == ComparisonOperator.CONTAINS:
            if not isinstance(left_val, Iterable):
                raise PredicateTypeError(
                    f"Left operand of 'contains' must be an iterable, got {type(left_val).__name__}"
                )
            is_contained = right_val in left_val
            return TriState.TRUE if is_contained else TriState.FALSE

        raise PredicateEvaluationError(f"Unsupported comparison operator '{op}'")

    raise PredicateEvaluationError(
        f"Unsupported predicate structure: {type(pred).__name__}"
    )
