from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import TriStateBool


class PredicateOperator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    EXISTS = "EXISTS"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"


class CompoundOperator(str, Enum):
    ALL = "ALL"  # Logical AND
    ANY = "ANY"  # Logical OR
    NOT = "NOT"  # Logical NOT


# Allowed path prefixes for safe deterministic evaluation
ALLOWLISTED_FIELD_PREFIXES = {
    "principal.",
    "tool_call.",
    "action.",
    "resource.",
    "approval.",
    "disclosure.",
    "effect.",
    "instruction.",
    "trace.",
    "context.",
}


class PredicateCondition(BaseModel):
    """Atomic safe declarative condition on an allowlisted evidence field."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(
        ...,
        description="Dotted path into evidence context, e.g. tool_call.arguments.amount",
    )
    operator: PredicateOperator = Field(
        ..., description="Allowlisted comparison operator"
    )
    value: Any | None = Field(
        default=None,
        description="Target literal value (string, integer minor units, decimal string, list, boolean, null)",
    )


class CompoundPredicate(BaseModel):
    """Compound predicate supporting ALL, ANY, and NOT combinations."""

    model_config = ConfigDict(extra="forbid")

    operator: CompoundOperator = Field(
        default=CompoundOperator.ALL, description="Compound boolean operator"
    )
    conditions: list[Union[PredicateCondition, "CompoundPredicate"]] = Field(
        default_factory=list,
        description="List of atomic conditions or nested compound predicates",
    )


# Update forward references for recursive model
CompoundPredicate.model_rebuild()


def tri_and(a: TriStateBool, b: TriStateBool) -> TriStateBool:
    """Kleene 3-valued AND logic."""
    if a == TriStateBool.FALSE or b == TriStateBool.FALSE:
        return TriStateBool.FALSE
    if a == TriStateBool.UNKNOWN or b == TriStateBool.UNKNOWN:
        return TriStateBool.UNKNOWN
    return TriStateBool.TRUE


def tri_or(a: TriStateBool, b: TriStateBool) -> TriStateBool:
    """Kleene 3-valued OR logic."""
    if a == TriStateBool.TRUE or b == TriStateBool.TRUE:
        return TriStateBool.TRUE
    if a == TriStateBool.UNKNOWN or b == TriStateBool.UNKNOWN:
        return TriStateBool.UNKNOWN
    return TriStateBool.FALSE


def tri_not(a: TriStateBool) -> TriStateBool:
    """Kleene 3-valued NOT logic."""
    if a == TriStateBool.TRUE:
        return TriStateBool.FALSE
    if a == TriStateBool.FALSE:
        return TriStateBool.TRUE
    return TriStateBool.UNKNOWN
