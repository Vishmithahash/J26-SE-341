"""Tests for safe declarative predicates, three-valued Kleene logic, and explicit scopes."""

import pytest

from app.components.c2_state_aware_workflow.predicates import (
    MISSING,
    ComparisonOperator,
    ComparisonPredicate,
    EvaluationContext,
    FieldRef,
    PredicateTypeError,
    PresenceOperator,
    PresencePredicate,
    ScopeEnum,
    TriState,
    VariableUpdate,
    VariableUpdateOp,
    evaluate_predicate,
)


def test_three_valued_kleene_and():
    # FALSE AND UNKNOWN = FALSE
    assert (TriState.FALSE & TriState.UNKNOWN) == TriState.FALSE
    assert (TriState.UNKNOWN & TriState.FALSE) == TriState.FALSE

    # TRUE AND UNKNOWN = UNKNOWN
    assert (TriState.TRUE & TriState.UNKNOWN) == TriState.UNKNOWN
    assert (TriState.UNKNOWN & TriState.TRUE) == TriState.UNKNOWN

    # UNKNOWN AND UNKNOWN = UNKNOWN
    assert (TriState.UNKNOWN & TriState.UNKNOWN) == TriState.UNKNOWN

    # Standard boolean cases
    assert (TriState.TRUE & TriState.TRUE) == TriState.TRUE
    assert (TriState.FALSE & TriState.TRUE) == TriState.FALSE


def test_three_valued_kleene_or():
    # TRUE OR UNKNOWN = TRUE
    assert (TriState.TRUE | TriState.UNKNOWN) == TriState.TRUE
    assert (TriState.UNKNOWN | TriState.TRUE) == TriState.TRUE

    # FALSE OR UNKNOWN = UNKNOWN
    assert (TriState.FALSE | TriState.UNKNOWN) == TriState.UNKNOWN
    assert (TriState.UNKNOWN | TriState.FALSE) == TriState.UNKNOWN

    # UNKNOWN OR UNKNOWN = UNKNOWN
    assert (TriState.UNKNOWN | TriState.UNKNOWN) == TriState.UNKNOWN

    # Standard boolean cases
    assert (TriState.FALSE | TriState.FALSE) == TriState.FALSE
    assert (TriState.TRUE | TriState.FALSE) == TriState.TRUE


def test_three_valued_kleene_not():
    # NOT UNKNOWN = UNKNOWN
    assert (~TriState.UNKNOWN) == TriState.UNKNOWN
    assert TriState.UNKNOWN.lnot() == TriState.UNKNOWN

    # NOT TRUE = FALSE, NOT FALSE = TRUE
    assert (~TriState.TRUE) == TriState.FALSE
    assert (~TriState.FALSE) == TriState.TRUE


def test_tristate_forbids_python_truthiness():
    with pytest.raises(TypeError) as exc_info:
        if TriState.TRUE:
            pass
    assert "Direct boolean coercion of TriState is forbidden" in str(exc_info.value)


def test_explicit_null_vs_missing_observation():
    # Context where 'order.status' is explicitly None (explicit null)
    # Context where 'shipping' is omitted entirely (missing)
    context = EvaluationContext(
        event={"tool": "refund"},
        before={"order": {"id": 100, "status": None}},
        after={"order": {"id": 100, "status": "REFUNDED"}},
    )

    # 1. Resolving before.order.status -> explicit None
    val_status = context.resolve(FieldRef(scope=ScopeEnum.BEFORE, path="order.status"))
    assert val_status is None

    # 2. Resolving before.shipping.carrier -> MISSING
    val_shipping = context.resolve(
        FieldRef(scope=ScopeEnum.BEFORE, path="shipping.carrier")
    )
    assert val_shipping is MISSING

    # 3. Presence checks on explicit null
    pred_null_is_null = PresencePredicate(
        target=FieldRef(scope=ScopeEnum.BEFORE, path="order.status"),
        op=PresenceOperator.IS_NULL,
    )
    assert evaluate_predicate(pred_null_is_null, context) == TriState.TRUE

    pred_null_exists = PresencePredicate(
        target=FieldRef(scope=ScopeEnum.BEFORE, path="order.status"),
        op=PresenceOperator.EXISTS,
    )
    assert evaluate_predicate(pred_null_exists, context) == TriState.TRUE

    # 4. Presence checks on MISSING observation
    pred_miss_exists = PresencePredicate(
        target=FieldRef(scope=ScopeEnum.BEFORE, path="shipping.carrier"),
        op=PresenceOperator.EXISTS,
    )
    assert evaluate_predicate(pred_miss_exists, context) == TriState.FALSE

    pred_miss_not_exists = PresencePredicate(
        target=FieldRef(scope=ScopeEnum.BEFORE, path="shipping.carrier"),
        op=PresenceOperator.NOT_EXISTS,
    )
    assert evaluate_predicate(pred_miss_not_exists, context) == TriState.TRUE

    pred_miss_is_null = PresencePredicate(
        target=FieldRef(scope=ScopeEnum.BEFORE, path="shipping.carrier"),
        op=PresenceOperator.IS_NULL,
    )
    # In three-valued logic, missing observation yields UNKNOWN for is_null
    assert evaluate_predicate(pred_miss_is_null, context) == TriState.UNKNOWN


def test_missing_observation_in_comparison_yields_unknown():
    context = EvaluationContext(
        before={"order": {"id": 501}},
    )

    # Comparing a missing field against a literal yields UNKNOWN
    pred = ComparisonPredicate(
        left=FieldRef(scope=ScopeEnum.BEFORE, path="order.status"),
        op=ComparisonOperator.EQUALS,
        right="PAID",
    )
    assert evaluate_predicate(pred, context) == TriState.UNKNOWN


def test_type_validation_rejects_incompatible_comparison():
    context = EvaluationContext(
        event={"count": "twenty"},
    )
    pred = ComparisonPredicate(
        left=FieldRef(scope=ScopeEnum.EVENT, path="count"),
        op=ComparisonOperator.LESS_THAN,
        right=10,
    )
    with pytest.raises(PredicateTypeError) as exc_info:
        evaluate_predicate(pred, context)
    assert "Incompatible types for comparison '<'" in str(exc_info.value)


def test_variable_updates():
    context = EvaluationContext(
        event={"params": {"order_id": 503}},
        variables={"counter": 1, "items": ["item1"]},
    )

    # SET
    context.apply_update(
        VariableUpdate(
            target_var="selected_order_id",
            op=VariableUpdateOp.SET,
            source_ref=FieldRef(scope=ScopeEnum.EVENT, path="params.order_id"),
        )
    )
    assert context.scopes[ScopeEnum.VARS]["selected_order_id"] == 503

    # INCREMENT
    context.apply_update(
        VariableUpdate(
            target_var="counter",
            op=VariableUpdateOp.INCREMENT,
            literal_value=2,
        )
    )
    assert context.scopes[ScopeEnum.VARS]["counter"] == 3

    # APPEND
    context.apply_update(
        VariableUpdate(
            target_var="items",
            op=VariableUpdateOp.APPEND,
            literal_value="item2",
        )
    )
    assert context.scopes[ScopeEnum.VARS]["items"] == ["item1", "item2"]

    # DELETE
    context.apply_update(
        VariableUpdate(
            target_var="counter",
            op=VariableUpdateOp.DELETE,
        )
    )
    assert "counter" not in context.scopes[ScopeEnum.VARS]
