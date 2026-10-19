from decimal import Decimal

from app.components.c4_policy_aware_safety.contracts.enums import TriStateBool
from app.components.c4_policy_aware_safety.contracts.predicates import (
    CompoundOperator,
    CompoundPredicate,
    PredicateCondition,
    PredicateOperator,
    tri_and,
    tri_not,
    tri_or,
)
from app.components.c4_policy_aware_safety.predicates.evaluator import (
    evaluate_compound_predicate,
    evaluate_condition,
    resolve_field_path,
)


def test_resolve_field_path_preserves_special_values():
    data = {
        "tool_call": {
            "name": "refund",
            "arguments": {
                "amount": 0,
                "explicit_null": None,
                "is_active": False,
                "tags": [],
            },
        }
    }

    # Missing field
    assert resolve_field_path(data, "tool_call.arguments.missing_field") is not None
    from app.components.c4_policy_aware_safety.predicates.evaluator import _MISSING

    assert resolve_field_path(data, "tool_call.arguments.missing_field") is _MISSING

    # Zero preserved (not missing)
    assert resolve_field_path(data, "tool_call.arguments.amount") == 0

    # Explicit null preserved
    assert resolve_field_path(data, "tool_call.arguments.explicit_null") is None

    # False preserved
    assert resolve_field_path(data, "tool_call.arguments.is_active") is False

    # Empty list preserved
    assert resolve_field_path(data, "tool_call.arguments.tags") == []


def test_kleene_three_valued_logic_truth_tables():
    T = TriStateBool.TRUE
    F = TriStateBool.FALSE
    U = TriStateBool.UNKNOWN

    # AND
    assert tri_and(T, T) == T
    assert tri_and(T, F) == F
    assert tri_and(F, T) == F
    assert tri_and(F, F) == F
    assert tri_and(T, U) == U
    assert tri_and(U, T) == U
    assert tri_and(F, U) == F  # False and unknown is definitely False
    assert tri_and(U, F) == F
    assert tri_and(U, U) == U

    # OR
    assert tri_or(T, T) == T
    assert tri_or(T, F) == T
    assert tri_or(F, T) == T
    assert tri_or(F, F) == F
    assert tri_or(T, U) == T  # True or unknown is definitely True
    assert tri_or(U, T) == T
    assert tri_or(F, U) == U
    assert tri_or(U, F) == U
    assert tri_or(U, U) == U

    # NOT
    assert tri_not(T) == F
    assert tri_not(F) == T
    assert tri_not(U) == U


def test_missing_field_produces_unknown_not_false_or_zero():
    # If a decision depends on a missing field, it must evaluate to UNKNOWN
    data = {"tool_call": {"arguments": {}}}

    cond_gt = PredicateCondition(
        field="tool_call.arguments.amount",
        operator=PredicateOperator.GREATER_THAN,
        value=5000,
    )
    assert evaluate_condition(cond_gt, data) == TriStateBool.UNKNOWN

    cond_eq = PredicateCondition(
        field="tool_call.arguments.amount",
        operator=PredicateOperator.EQUALS,
        value=0,
    )
    # Missing value does NOT equal zero!
    assert evaluate_condition(cond_eq, data) == TriStateBool.UNKNOWN

    cond_exists = PredicateCondition(
        field="tool_call.arguments.amount",
        operator=PredicateOperator.EXISTS,
    )
    assert evaluate_condition(cond_exists, data) == TriStateBool.FALSE


def test_zero_and_null_distinct_from_missing():
    data = {
        "tool_call": {
            "arguments": {
                "amount": 0,
                "reason": None,
            }
        }
    }

    # 0 equals 0
    cond_zero = PredicateCondition(
        field="tool_call.arguments.amount",
        operator=PredicateOperator.EQUALS,
        value=0,
    )
    assert evaluate_condition(cond_zero, data) == TriStateBool.TRUE

    # 0 is not greater than 5000 (evaluates to FALSE, NOT UNKNOWN!)
    cond_gt = PredicateCondition(
        field="tool_call.arguments.amount",
        operator=PredicateOperator.GREATER_THAN,
        value=5000,
    )
    assert evaluate_condition(cond_gt, data) == TriStateBool.FALSE

    # reason is null
    cond_null = PredicateCondition(
        field="tool_call.arguments.reason",
        operator=PredicateOperator.IS_NULL,
    )
    assert evaluate_condition(cond_null, data) == TriStateBool.TRUE

    cond_not_null = PredicateCondition(
        field="tool_call.arguments.reason",
        operator=PredicateOperator.IS_NOT_NULL,
    )
    assert evaluate_condition(cond_not_null, data) == TriStateBool.FALSE


def test_monetary_decimal_and_minor_units():
    data = {
        "tool_call": {
            "arguments": {
                "amount_cents": 5000,
                "amount_str": "50.00",
                "amount_dec": Decimal("200.00"),
            }
        }
    }

    # Integer minor units comparison
    cond1 = PredicateCondition(
        field="tool_call.arguments.amount_cents",
        operator=PredicateOperator.GREATER_THAN,
        value=2000,
    )
    assert evaluate_condition(cond1, data) == TriStateBool.TRUE

    # String decimal comparison avoids float precision issues
    cond2 = PredicateCondition(
        field="tool_call.arguments.amount_str",
        operator=PredicateOperator.EQUALS,
        value="50.0",
    )
    assert evaluate_condition(cond2, data) == TriStateBool.TRUE

    # Decimal comparison
    cond3 = PredicateCondition(
        field="tool_call.arguments.amount_dec",
        operator=PredicateOperator.GREATER_THAN,
        value="100.00",
    )
    assert evaluate_condition(cond3, data) == TriStateBool.TRUE


def test_membership_and_containment():
    data = {
        "principal": {
            "roles": ["CUSTOMER_SUPPORT", "TIER_1"],
        },
        "disclosure": {
            "marker": "CANARY_TOKEN_XYZ",
            "recipient": "external_user",
        },
    }

    # IN operator
    cond_in = PredicateCondition(
        field="principal.roles",
        operator=PredicateOperator.CONTAINS,
        value="CUSTOMER_SUPPORT",
    )
    assert evaluate_condition(cond_in, data) == TriStateBool.TRUE

    cond_not_in = PredicateCondition(
        field="principal.roles",
        operator=PredicateOperator.CONTAINS,
        value="MANAGER",
    )
    assert evaluate_condition(cond_not_in, data) == TriStateBool.FALSE


def test_unallowlisted_field_rejected():
    data = {"system_hack": {"exec": "rm -rf"}}

    cond = PredicateCondition(
        field="system_hack.exec",
        operator=PredicateOperator.EQUALS,
        value="rm -rf",
    )
    # Does not have allowlisted prefix
    assert evaluate_condition(cond, data) == TriStateBool.UNKNOWN


def test_compound_predicate_short_circuit_and_nesting():
    data = {
        "tool_call": {
            "arguments": {"amount": 20000},
        },
        "approval": {
            "status": "APPROVED",
            "approver_role": "MANAGER",
        },
    }

    compound = CompoundPredicate(
        operator=CompoundOperator.ALL,
        conditions=[
            PredicateCondition(
                field="tool_call.arguments.amount",
                operator=PredicateOperator.GREATER_THAN,
                value=5000,
            ),
            PredicateCondition(
                field="approval.status",
                operator=PredicateOperator.EQUALS,
                value="APPROVED",
            ),
            PredicateCondition(
                field="approval.approver_role",
                operator=PredicateOperator.EQUALS,
                value="MANAGER",
            ),
        ],
    )

    assert evaluate_compound_predicate(compound, data) == TriStateBool.TRUE
