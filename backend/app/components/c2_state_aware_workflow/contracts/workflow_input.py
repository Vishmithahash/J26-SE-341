"""Workflow input contract for C2: State-Aware Multi-Step Workflow Testing.

Defines the structured requirements, business rules, tool specifications,
observable-state mappings, and synthetic fixture references.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolParameterSpec(BaseModel):
    """Specification of an accepted parameter for a tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: str = Field(
        ...,
        description="Data type: 'string', 'integer', 'float', 'boolean', 'dict', 'list'",
    )
    description: str | None = None
    required: bool = True
    default: Any = None


class ToolSpecification(BaseModel):
    """Specification of an executable tool/API available to the agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str
    description: str
    parameters: list[ToolParameterSpec] = Field(default_factory=list)
    return_type: str = "dict"
    has_side_effects: bool = False


class ObservableStateMapping(BaseModel):
    """Mapping of domain entities and fields to observable application state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: str = Field(..., description="E.g. 'orders', 'payments', 'refunds'")
    primary_key: str = Field(default="id")
    observable_fields: list[str] = Field(
        default_factory=list,
        description="List of fields observed before and after events, e.g. ['status', 'customer_id']",
    )
    description: str | None = None


RuleCategory = Literal[
    "eligibility", "ordering", "rejection", "effect", "invariant", "milestone"
]


class BusinessRule(BaseModel):
    """Domain business rule governing the workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    name: str
    description: str
    category: RuleCategory
    priority: int = 1


class SyntheticFixtureReference(BaseModel):
    """Reference to a synthetic resettable fixture for testing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_id: str
    description: str
    initial_entities: dict[str, Any] = Field(default_factory=dict)
    protected_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Keys/fields that must remain untouched under failure or rejection",
    )


class WorkflowInputContract(BaseModel):
    """Complete structured workflow input provided to C2 for model construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    project_id: str
    domain: str = Field(
        ..., description="Domain name, e.g. 'ecommerce', 'flight_booking', 'lms'"
    )
    workflow_id: str
    name: str
    version: str = "1.0.0"
    task: str = Field(
        ..., description="Natural language goal or task prompt given to the agent"
    )
    business_rules: list[BusinessRule] = Field(default_factory=list)
    tool_specifications: list[ToolSpecification] = Field(default_factory=list)
    observable_state_mappings: list[ObservableStateMapping] = Field(
        default_factory=list
    )
    synthetic_fixture: SyntheticFixtureReference
    assumptions: list[str] = Field(default_factory=list)
