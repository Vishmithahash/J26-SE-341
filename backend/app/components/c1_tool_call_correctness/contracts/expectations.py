from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)


class ComparisonOperator(str, Enum):
    """Bounded declarative operators for argument value constraints.
    Arbitrary script/SQL/eval execution is strictly prohibited.
    """

    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    IN_SET = "IN_SET"
    NOT_IN_SET = "NOT_IN_SET"
    REGEX_MATCH = "REGEX_MATCH"
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    TYPE_EQUALS = "TYPE_EQUALS"


class FieldPresence(str, Enum):
    """Explicitly distinguishes missing fields from explicitly null fields in argument payloads."""

    ALLOWED = "ALLOWED"  # Field may be omitted, null, or present with value
    REQUIRED_NON_NULL = (
        "REQUIRED_NON_NULL"  # Field must be present and value must not be null
    )
    REQUIRED_EXPLICIT_NULL = "REQUIRED_EXPLICIT_NULL"  # Field key must exist in dictionary with null/None value
    REQUIRED_PRESENT = "REQUIRED_PRESENT"  # Field key must exist in dictionary (value can be null or non-null)
    FORBIDDEN_OR_MISSING = (
        "FORBIDDEN_OR_MISSING"  # Field key must not exist in arguments dictionary
    )


class FieldPresenceState(str, Enum):
    """Runtime classification of an argument field in a tool call."""

    MISSING = "MISSING"  # Key is not present in the dictionary
    EXPLICIT_NULL = "EXPLICIT_NULL"  # Key is present and value is None
    PRESENT_NON_NULL = "PRESENT_NON_NULL"  # Key is present and value is not None

    @classmethod
    def inspect(cls, data: dict[str, Any], key: str) -> "FieldPresenceState":
        if key not in data:
            return cls.MISSING
        if data[key] is None:
            return cls.EXPLICIT_NULL
        return cls.PRESENT_NON_NULL

    def satisfies(self, expected: FieldPresence) -> bool:
        if expected == FieldPresence.ALLOWED:
            return True
        if expected == FieldPresence.REQUIRED_NON_NULL:
            return self == FieldPresenceState.PRESENT_NON_NULL
        if expected == FieldPresence.REQUIRED_EXPLICIT_NULL:
            return self == FieldPresenceState.EXPLICIT_NULL
        if expected == FieldPresence.REQUIRED_PRESENT:
            return self in (
                FieldPresenceState.PRESENT_NON_NULL,
                FieldPresenceState.EXPLICIT_NULL,
            )
        if expected == FieldPresence.FORBIDDEN_OR_MISSING:
            return self == FieldPresenceState.MISSING
        return False


class SourceRelationshipType(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    SUBSET_OF = "SUBSET_OF"
    CASE_INSENSITIVE_MATCH = "CASE_INSENSITIVE_MATCH"
    NUMERIC_TOLERANCE = "NUMERIC_TOLERANCE"


class SourceDataRelationship(BaseModel):
    """Declarative binding linking a tool argument to a known source or fixture record."""

    source_record_id: str = Field(
        ..., description="Stable ID of the source or fixture record"
    )
    source_path: str = Field(
        ...,
        description="Dotted path or property key in the source record (e.g. 'order.total')",
    )
    relationship_type: SourceRelationshipType = Field(
        default=SourceRelationshipType.EXACT_MATCH,
        description="Type of matching expected against the source value",
    )
    tolerance: float | None = Field(
        default=None,
        description="Permitted numeric delta when relationship_type is NUMERIC_TOLERANCE",
    )


class ArgumentConstraint(BaseModel):
    """Declarative rule for a specific tool argument."""

    argument_name: str = Field(
        ..., min_length=1, description="Target argument parameter name"
    )
    presence: FieldPresence = Field(
        default=FieldPresence.REQUIRED_NON_NULL,
        description="Requirement regarding field existence and nullability",
    )
    expected_type: str | None = Field(
        default=None,
        description="Expected JSON primitive type: 'string', 'number', 'integer', 'boolean', 'array', 'object'",
    )
    operator: ComparisonOperator | None = Field(
        default=None, description="Bounded comparison operator for argument value"
    )
    expected_value: Any = Field(
        default=None,
        description="Static expected value or permitted set for comparison",
    )
    source_relationship: SourceDataRelationship | None = Field(
        default=None,
        description="Relationship to a record in contextual source data or fixture",
    )
    requirement_refs: list[str] = Field(
        default_factory=list,
        description="IDs of task requirements justifying this argument constraint",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "argument_path" in data and "argument_name" not in data:
                data["argument_name"] = data["argument_path"]
            if "expected_presence" in data and "presence" not in data:
                data["presence"] = data["expected_presence"]
        return data

    @property
    def argument_path(self) -> str:
        return self.argument_name

    @property
    def expected_presence(self) -> FieldPresence:
        return self.presence


class ToolSelectionExpectation(BaseModel):
    """Declarative expectation on whether and how often a tool should be selected."""

    tool_name: str = Field(..., min_length=1, description="Target tool name")
    is_required: bool = Field(
        default=True, description="Whether tool invocation is mandatory"
    )
    min_count: int = Field(default=1, ge=0, description="Minimum expected invocations")
    max_count: int | None = Field(
        default=None, ge=1, description="Maximum permitted invocations"
    )
    must_precede_tools: list[str] = Field(
        default_factory=list,
        description="Tool names that must only be invoked AFTER this tool has executed",
    )
    requirement_refs: list[str] = Field(
        default_factory=list,
        description="IDs of task requirements justifying this selection constraint",
    )


class EvidenceRequirement(BaseModel):
    """Specifies evidence channels that must be collected to evaluate a check."""

    channel: EvidenceChannel = Field(..., description="Required evidence channel")
    required_for_checks: list[str] = Field(
        default_factory=list,
        description="List of check rule names or IDs that mandate this evidence channel",
    )
    description: str | None = Field(
        default=None, description="Purpose of this evidence collection"
    )


class ExpectationSuite(BaseModel):
    """Collection of declarative expectations for a configuration or test case."""

    tool_selections: list[ToolSelectionExpectation] = Field(
        default_factory=list, description="Tool selection expectations"
    )
    argument_constraints: dict[str, list[ArgumentConstraint]] = Field(
        default_factory=dict,
        description="Mapping from tool_name to its list of argument constraints",
    )
    evidence_requirements: list[EvidenceRequirement] = Field(
        default_factory=list, description="Evidence recording prerequisites"
    )
