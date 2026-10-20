"""Structured declarative predicate and update models.

NO eval, exec, SQL, or arbitrary code execution is permitted.
All conditions are expressed as structured trees with validated field references
and explicit scopes: event, vars, fixture, before, after.
"""

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScopeEnum(str, Enum):
    EVENT = "event"
    VARS = "vars"
    FIXTURE = "fixture"
    BEFORE = "before"
    AFTER = "after"


class ComparisonOperator(str, Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


class PresenceOperator(str, Enum):
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class FieldRef(BaseModel):
    """Reference to a field within an explicit evaluation scope.

    Example: scope="event", path="params.order_id"
    or path="order_id" (where path can be dotted for nested traversal).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: ScopeEnum
    path: str = Field(
        ..., description="Dotted path within the scope dictionary, e.g. 'order.status'"
    )

    @property
    def full_path(self) -> str:
        return f"{self.scope.value}.{self.path}" if self.path else self.scope.value


class ComparisonPredicate(BaseModel):
    """Binary comparison between a field/literal and another field/literal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["comparison"] = "comparison"
    left: FieldRef | Any = Field(..., description="FieldRef or literal value")
    op: ComparisonOperator
    right: FieldRef | Any = Field(..., description="FieldRef or literal value")


class PresencePredicate(BaseModel):
    """Presence and nullness check for a specific field reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["presence"] = "presence"
    target: FieldRef
    op: PresenceOperator


class LogicalPredicate(BaseModel):
    """Boolean composition: AND, OR, NOT."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["logical"] = "logical"
    op: LogicalOperator
    clauses: list["StructuredPredicate"] = Field(
        default_factory=list,
        description="List of child predicates for AND/OR. For NOT, must have exactly one clause.",
    )


class LiteralPredicate(BaseModel):
    """Literal tri-state or boolean outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["literal"] = "literal"
    value: Literal["TRUE", "FALSE", "UNKNOWN"]


# Discriminated union of all predicate types
StructuredPredicate = Annotated[
    ComparisonPredicate | PresencePredicate | LogicalPredicate | LiteralPredicate,
    Field(discriminator="type"),
]


class VariableUpdateOp(str, Enum):
    SET = "SET"
    INCREMENT = "INCREMENT"
    APPEND = "APPEND"
    DELETE = "DELETE"


class VariableUpdate(BaseModel):
    """Declarative binding/update of a state variable.

    Example: target_var='selected_order_id', op='SET', source_ref=FieldRef(scope='event', path='params.order_id')
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_var: str = Field(..., description="Name of the bound variable in 'vars'")
    op: VariableUpdateOp = Field(default=VariableUpdateOp.SET)
    source_ref: FieldRef | None = None
    literal_value: Any = None
    description: str | None = None
