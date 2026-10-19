from decimal import Decimal, InvalidOperation
from typing import Any

from app.components.c4_policy_aware_safety.contracts.enums import TriStateBool
from app.components.c4_policy_aware_safety.contracts.predicates import (
    ALLOWLISTED_FIELD_PREFIXES,
    CompoundOperator,
    CompoundPredicate,
    PredicateCondition,
    PredicateOperator,
    tri_and,
    tri_not,
    tri_or,
)

# Explicit sentinel for absent evidence fields
_MISSING = object()


def _is_numeric(val: Any) -> bool:
    if isinstance(val, (int, float, Decimal)):
        return True
    if isinstance(val, str):
        try:
            Decimal(val)
            return True
        except (InvalidOperation, ValueError):
            return False
    return False


def _to_decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def resolve_field_path(data: dict[str, Any], path: str) -> Any:
    """Safely traverse a dotted path in evidence data.

    Returns _MISSING sentinel if the key path does not exist.
    Preserves None, False, 0, and empty collections.
    """
    parts = path.split(".")
    current: Any = data

    for part in parts:
        if current is _MISSING or current is None:
            return _MISSING
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return _MISSING
        elif hasattr(current, part):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, list):
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return _MISSING
            except (ValueError, IndexError):
                return _MISSING
        else:
            return _MISSING

    return current


def evaluate_condition(
    condition: PredicateCondition, data: dict[str, Any]
) -> TriStateBool:
    """Evaluate an atomic predicate condition against evidence data with 3-valued logic."""
    # Enforce field allowlist prefix
    field = condition.field
    if not any(field.startswith(prefix) for prefix in ALLOWLISTED_FIELD_PREFIXES):
        # Unrecognized field path cannot be evaluated safely
        return TriStateBool.UNKNOWN

    actual = resolve_field_path(data, field)
    op = condition.operator
    target = condition.value

    # 1. Existence / Presence operators
    if op == PredicateOperator.EXISTS:
        # If field was absent from dictionary, it is FALSE. If present (even if None, 0, False, []), it is TRUE.
        return TriStateBool.FALSE if actual is _MISSING else TriStateBool.TRUE

    if op == PredicateOperator.IS_NULL:
        if actual is _MISSING:
            return TriStateBool.UNKNOWN
        return TriStateBool.TRUE if actual is None else TriStateBool.FALSE

    if op == PredicateOperator.IS_NOT_NULL:
        if actual is _MISSING:
            return TriStateBool.UNKNOWN
        return TriStateBool.FALSE if actual is None else TriStateBool.TRUE

    # 2. Missing evidence for any value-dependent operator produces UNKNOWN
    if actual is _MISSING:
        return TriStateBool.UNKNOWN

    # 3. Value-dependent operators
    if op == PredicateOperator.EQUALS:
        if actual is None and target is None:
            return TriStateBool.TRUE
        if actual is None or target is None:
            return TriStateBool.FALSE
        if _is_numeric(actual) and _is_numeric(target):
            try:
                return (
                    TriStateBool.TRUE
                    if _to_decimal(actual) == _to_decimal(target)
                    else TriStateBool.FALSE
                )
            except (InvalidOperation, TypeError, ValueError):
                return TriStateBool.FALSE
        return TriStateBool.TRUE if actual == target else TriStateBool.FALSE

    if op == PredicateOperator.NOT_EQUALS:
        eq_res = evaluate_condition(
            PredicateCondition(
                field=field, operator=PredicateOperator.EQUALS, value=target
            ),
            data,
        )
        return tri_not(eq_res)

    # 4. Ordered comparisons
    if op in (
        PredicateOperator.GREATER_THAN,
        PredicateOperator.GREATER_THAN_OR_EQUAL,
        PredicateOperator.LESS_THAN,
        PredicateOperator.LESS_THAN_OR_EQUAL,
    ):
        if actual is None or target is None:
            return TriStateBool.UNKNOWN

        if _is_numeric(actual) and _is_numeric(target):
            try:
                dec_actual = _to_decimal(actual)
                dec_target = _to_decimal(target)
                if op == PredicateOperator.GREATER_THAN:
                    return (
                        TriStateBool.TRUE
                        if dec_actual > dec_target
                        else TriStateBool.FALSE
                    )
                if op == PredicateOperator.GREATER_THAN_OR_EQUAL:
                    return (
                        TriStateBool.TRUE
                        if dec_actual >= dec_target
                        else TriStateBool.FALSE
                    )
                if op == PredicateOperator.LESS_THAN:
                    return (
                        TriStateBool.TRUE
                        if dec_actual < dec_target
                        else TriStateBool.FALSE
                    )
                if op == PredicateOperator.LESS_THAN_OR_EQUAL:
                    return (
                        TriStateBool.TRUE
                        if dec_actual <= dec_target
                        else TriStateBool.FALSE
                    )
            except (InvalidOperation, TypeError, ValueError):
                return TriStateBool.UNKNOWN
        return TriStateBool.UNKNOWN

    # 5. Membership operators
    if op == PredicateOperator.IN:
        if not isinstance(target, (list, tuple, set)):
            return TriStateBool.UNKNOWN
        # Check membership with numeric normalization
        if _is_numeric(actual):
            try:
                dec_actual = _to_decimal(actual)
                for item in target:
                    if _is_numeric(item) and dec_actual == _to_decimal(item):
                        return TriStateBool.TRUE
            except (InvalidOperation, TypeError, ValueError):
                pass
        return TriStateBool.TRUE if actual in target else TriStateBool.FALSE

    if op == PredicateOperator.NOT_IN:
        in_res = evaluate_condition(
            PredicateCondition(
                field=field, operator=PredicateOperator.IN, value=target
            ),
            data,
        )
        return tri_not(in_res)

    if op == PredicateOperator.CONTAINS:
        if actual is None:
            return TriStateBool.FALSE
        if isinstance(actual, (list, tuple, set)):
            if _is_numeric(target):
                try:
                    dec_target = _to_decimal(target)
                    for item in actual:
                        if _is_numeric(item) and dec_target == _to_decimal(item):
                            return TriStateBool.TRUE
                except (InvalidOperation, TypeError, ValueError):
                    pass
            return TriStateBool.TRUE if target in actual else TriStateBool.FALSE
        if isinstance(actual, str):
            return TriStateBool.TRUE if str(target) in actual else TriStateBool.FALSE
        return TriStateBool.FALSE

    return TriStateBool.UNKNOWN


def evaluate_compound_predicate(
    predicate: PredicateCondition | CompoundPredicate,
    data: dict[str, Any],
) -> TriStateBool:
    """Recursively evaluate a compound predicate using Kleene 3-valued logic."""
    if isinstance(predicate, PredicateCondition):
        return evaluate_condition(predicate, data)

    op = predicate.operator
    conditions = predicate.conditions

    if op == CompoundOperator.ALL:
        if not conditions:
            return TriStateBool.TRUE
        result = TriStateBool.TRUE
        for cond in conditions:
            sub = evaluate_compound_predicate(cond, data)
            result = tri_and(result, sub)
            # Short-circuit if FALSE in Kleene logic (FALSE and anything is FALSE)
            if result == TriStateBool.FALSE:
                return TriStateBool.FALSE
        return result

    if op == CompoundOperator.ANY:
        if not conditions:
            return TriStateBool.FALSE
        result = TriStateBool.FALSE
        for cond in conditions:
            sub = evaluate_compound_predicate(cond, data)
            result = tri_or(result, sub)
            # Short-circuit if TRUE in Kleene logic (TRUE or anything is TRUE)
            if result == TriStateBool.TRUE:
                return TriStateBool.TRUE
        return result

    if op == CompoundOperator.NOT:
        if not conditions:
            return TriStateBool.UNKNOWN
        # NOT wraps conjunction of sub-conditions
        if len(conditions) == 1:
            return tri_not(evaluate_compound_predicate(conditions[0], data))
        all_res = TriStateBool.TRUE
        for cond in conditions:
            all_res = tri_and(all_res, evaluate_compound_predicate(cond, data))
        return tri_not(all_res)

    return TriStateBool.UNKNOWN
