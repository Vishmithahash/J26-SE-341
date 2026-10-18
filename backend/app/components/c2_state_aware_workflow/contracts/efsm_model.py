"""EFSM / FSM workflow model definition contract for C2.

Represents states, transitions, guards, bindings, invariants, milestones,
entity continuity, expected effects, protected fields, and final outcomes.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.predicates.expressions import (
    StructuredPredicate,
    VariableUpdate,
)


class StateType(str, Enum):
    INITIAL = "initial"
    INTERMEDIATE = "intermediate"
    TERMINAL_ACCEPTING = "terminal_accepting"
    TERMINAL_REJECTION = "terminal_rejection"


class StateDefinition(BaseModel):
    """A distinct state in the workflow model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ..., description="Unique state identifier, e.g. 'START', 'REFUNDED'"
    )
    name: str
    type: StateType
    description: str | None = None
    milestone: str | None = Field(
        default=None, description="Optional milestone name achieved upon entering"
    )


class VariableDeclaration(BaseModel):
    """A declared state variable used in guards and updates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Variable name, e.g. 'selected_order_id'")
    type: str = Field(
        ..., description="'string', 'integer', 'float', 'boolean', 'list', 'dict'"
    )
    domain: list[Any] | None = Field(
        default=None,
        description="Optional finite domain values for bounded semantic validation",
    )
    initial_value: Any = None
    description: str | None = None


class TransitionDefinition(BaseModel):
    """A transition from source_state to target_state triggered by an event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., description="Unique transition identifier")
    source_state: str
    target_state: str
    trigger_event: str = Field(
        ..., description="Event or tool name triggering this transition"
    )
    guard: StructuredPredicate | None = Field(
        default=None,
        description="Structured predicate required to be TRUE to enable this transition",
    )
    actions: list[VariableUpdate] = Field(
        default_factory=list,
        description="Variable bindings or updates applied upon taking this transition",
    )
    expected_effects: list[StructuredPredicate] = Field(
        default_factory=list,
        description="Assertions that must hold over the state after the transition completes",
    )
    source_rules: list[str] = Field(
        default_factory=list,
        description="IDs of business rules justifying this transition",
    )
    description: str | None = None


class EventMapping(BaseModel):
    """Maps an abstract model event to a concrete tool call and parameter bindings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    tool_name: str
    parameter_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Map of model parameters to tool argument names",
    )
    description: str | None = None


class WorkflowInvariant(BaseModel):
    """Safety condition that must hold across all states or during specified phases."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    predicate: StructuredPredicate
    description: str | None = None
    source_rule: str | None = None


class MilestoneDefinition(BaseModel):
    """Key business milestone that must be achieved during a valid workflow execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    state_id: str
    required: bool = True
    description: str | None = None


class EntityContinuityRule(BaseModel):
    """Enforces that an entity identified in an early step remains consistent through subsequent steps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    entity_type: str = Field(..., description="E.g. 'order'")
    key_field: str = Field(..., description="E.g. 'order_id'")
    bound_variable: str = Field(..., description="E.g. 'selected_order_id'")
    description: str | None = None


class ProtectedField(BaseModel):
    """Application state field that must not be altered, particularly on rejection paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: str
    field_path: str
    allowed_mutations: list[str] = Field(
        default_factory=list,
        description="List of states/events where mutation is permitted. Empty means strict immutable.",
    )
    strict_unchanged_on_rejection: bool = True
    description: str | None = None


class FinalOutcome(BaseModel):
    """Declared terminal business outcome for the workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_id: str
    type: Literal["ACCEPTING", "REJECTION"]
    terminal_state_id: str
    description: str
    predicate: StructuredPredicate | None = None


class EFSMModelDefinition(BaseModel):
    """Complete versioned Extended Finite State Machine definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    project_id: str
    model_id: str
    version: str = "1.0.0"
    name: str
    description: str | None = None

    states: list[StateDefinition] = Field(..., min_length=2)
    initial_state_id: str
    accepting_state_ids: list[str] = Field(..., min_length=1)
    rejection_state_ids: list[str] = Field(default_factory=list)

    variables: list[VariableDeclaration] = Field(default_factory=list)
    transitions: list[TransitionDefinition] = Field(..., min_length=1)
    event_mappings: list[EventMapping] = Field(default_factory=list)
    invariants: list[WorkflowInvariant] = Field(default_factory=list)
    milestones: list[MilestoneDefinition] = Field(default_factory=list)
    entity_continuity_rules: list[EntityContinuityRule] = Field(default_factory=list)
    protected_fields: list[ProtectedField] = Field(default_factory=list)
    final_outcomes: list[FinalOutcome] = Field(default_factory=list)

    builder_version: str = "c2_deterministic_v1"
    assumptions: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
