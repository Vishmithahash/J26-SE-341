import re
from typing import Any

from app.components.c1_tool_call_correctness.contracts.expectations import (
    ComparisonOperator,
    FieldPresence,
    FieldPresenceState,
    SourceDataRelationship,
    SourceRelationshipType,
)


def extract_path_value(data: Any, path: str) -> tuple[bool, Any]:
    """Safely extracts a nested value from a dictionary using dot notation (e.g. 'order.total_amount').
    Does not use eval or arbitrary attribute access.
    """
    if not path:
        return True, data
    parts = path.strip().split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, (list, tuple)) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(curr):
                curr = curr[idx]
            else:
                return False, None
        else:
            return False, None
    return True, curr


def evaluate_argument_presence(
    actual_args: dict[str, Any], arg_name: str, presence_rule: FieldPresence
) -> tuple[bool, str]:
    """Evaluates whether an argument field satisfies the presence constraint.
    Explicitly distinguishes MISSING (key absent) from EXPLICIT_NULL (key present, value None).
    """
    state = FieldPresenceState.inspect(actual_args, arg_name)
    passed = state.satisfies(presence_rule)
    if passed:
        return (
            True,
            f"Field '{arg_name}' presence '{state.value}' satisfies requirement '{presence_rule.value}'.",
        )
    return False, (
        f"Field '{arg_name}' presence violation: observed '{state.value}', "
        f"expected '{presence_rule.value}'."
    )


def evaluate_operator(
    operator: ComparisonOperator, actual_value: Any, expected_value: Any
) -> tuple[bool, str]:
    """Bounded, safe declarative operator evaluation.
    Arbitrary script, expression, or command execution is never permitted.
    """
    try:
        if operator == ComparisonOperator.EQUALS:
            matched = actual_value == expected_value
            return matched, f"Expected {expected_value!r}, observed {actual_value!r}."

        elif operator == ComparisonOperator.NOT_EQUALS:
            matched = actual_value != expected_value
            return (
                matched,
                f"Expected not {expected_value!r}, observed {actual_value!r}.",
            )

        elif operator in (
            ComparisonOperator.GREATER_THAN,
            ComparisonOperator.LESS_THAN,
            ComparisonOperator.GREATER_EQUAL,
            ComparisonOperator.LESS_EQUAL,
        ):
            if actual_value is None or expected_value is None:
                return (
                    False,
                    f"Cannot compare NoneType using numeric operator '{operator.value}'.",
                )
            act = float(actual_value)
            exp = float(expected_value)
            if operator == ComparisonOperator.GREATER_THAN:
                matched = act > exp
            elif operator == ComparisonOperator.LESS_THAN:
                matched = act < exp
            elif operator == ComparisonOperator.GREATER_EQUAL:
                matched = act >= exp
            else:
                matched = act <= exp
            return matched, f"Comparison {act} {operator.value} {exp}: {matched}."

        elif operator == ComparisonOperator.IN_SET:
            if not isinstance(expected_value, (list, tuple, set)):
                return (
                    False,
                    f"Operator IN_SET expects a collection, got {type(expected_value).__name__}.",
                )
            matched = actual_value in expected_value
            return matched, f"Value {actual_value!r} in {expected_value!r}: {matched}."

        elif operator == ComparisonOperator.NOT_IN_SET:
            if not isinstance(expected_value, (list, tuple, set)):
                return (
                    False,
                    f"Operator NOT_IN_SET expects a collection, got {type(expected_value).__name__}.",
                )
            matched = actual_value not in expected_value
            return (
                matched,
                f"Value {actual_value!r} not in {expected_value!r}: {matched}.",
            )

        elif operator == ComparisonOperator.REGEX_MATCH:
            if actual_value is None or not isinstance(expected_value, str):
                return False, "REGEX_MATCH requires string actual and pattern values."
            matched = bool(re.search(expected_value, str(actual_value)))
            return (
                matched,
                f"Regex pattern r'{expected_value}' match against '{actual_value}': {matched}.",
            )

        elif operator == ComparisonOperator.CONTAINS:
            if actual_value is None:
                return False, "Cannot check CONTAINS on None."
            matched = str(expected_value) in str(actual_value)
            return matched, f"Substr '{expected_value}' in '{actual_value}': {matched}."

        elif operator == ComparisonOperator.STARTS_WITH:
            if actual_value is None:
                return False, "Cannot check STARTS_WITH on None."
            matched = str(actual_value).startswith(str(expected_value))
            return (
                matched,
                f"'{actual_value}' startswith '{expected_value}': {matched}.",
            )

        elif operator == ComparisonOperator.ENDS_WITH:
            if actual_value is None:
                return False, "Cannot check ENDS_WITH on None."
            matched = str(actual_value).endswith(str(expected_value))
            return matched, f"'{actual_value}' endswith '{expected_value}': {matched}."

        elif operator == ComparisonOperator.TYPE_EQUALS:
            type_map = {
                "string": str,
                "str": str,
                "integer": int,
                "int": int,
                "number": (int, float),
                "float": float,
                "boolean": bool,
                "bool": bool,
                "array": list,
                "list": list,
                "object": dict,
                "dict": dict,
            }
            exp_type_name = str(expected_value).lower()
            expected_py_type = type_map.get(exp_type_name)
            if not expected_py_type:
                return False, f"Unknown expected type name '{expected_value}'."
            # Note: in Python, bool is a subclass of int, so handle bool explicitly
            if expected_py_type in (int, float, (int, float)) and isinstance(
                actual_value, bool
            ):
                matched = False
            else:
                matched = isinstance(actual_value, expected_py_type)
            return (
                matched,
                f"Value type '{type(actual_value).__name__}' match with '{exp_type_name}': {matched}.",
            )

        return False, f"Unsupported comparison operator '{operator}'."

    except (ValueError, TypeError) as err:
        return False, f"Operator evaluation failed: {err}"


def evaluate_source_relationship(
    actual_value: Any,
    source_context: dict[str, Any],
    relationship: SourceDataRelationship,
) -> tuple[bool, str]:
    """Validates that an argument value matches or correlates with a known source or fixture record."""
    record_id = relationship.source_record_id
    if record_id not in source_context:
        return (
            False,
            f"Source record '{record_id}' not found in provided contextual data.",
        )

    record_data = source_context[record_id]
    found, source_value = extract_path_value(record_data, relationship.source_path)
    if not found:
        return (
            False,
            f"Path '{relationship.source_path}' not found in record '{record_id}'.",
        )

    if relationship.relationship_type == SourceRelationshipType.EXACT_MATCH:
        matched = actual_value == source_value
        return matched, f"Exact match expected {source_value!r}, got {actual_value!r}."

    elif (
        relationship.relationship_type == SourceRelationshipType.CASE_INSENSITIVE_MATCH
    ):
        act_str = str(actual_value).strip().lower() if actual_value is not None else ""
        src_str = str(source_value).strip().lower() if source_value is not None else ""
        matched = act_str == src_str
        return matched, f"Case-insensitive match '{src_str}' vs '{act_str}': {matched}."

    elif relationship.relationship_type == SourceRelationshipType.NUMERIC_TOLERANCE:
        tolerance = relationship.tolerance or 0.0
        try:
            diff = abs(float(actual_value) - float(source_value))
            matched = diff <= tolerance
            return (
                matched,
                f"Numeric delta {diff:.4f} within tolerance {tolerance} of {source_value}.",
            )
        except (ValueError, TypeError):
            return (
                False,
                f"Numeric tolerance comparison failed for '{actual_value}' and '{source_value}'.",
            )

    elif relationship.relationship_type == SourceRelationshipType.SUBSET_OF:
        if isinstance(source_value, (list, set, tuple)):
            matched = actual_value in source_value
            return (
                matched,
                f"Value {actual_value!r} subset of {source_value!r}: {matched}.",
            )
        elif isinstance(source_value, dict) and isinstance(actual_value, dict):
            matched = all(actual_value.get(k) == v for k, v in source_value.items())
            return matched, f"Dict subset match: {matched}."
        return (
            False,
            f"Unsupported subset_of types: {type(actual_value)} and {type(source_value)}.",
        )

    return (
        False,
        f"Unsupported source relationship type '{relationship.relationship_type}'.",
    )
