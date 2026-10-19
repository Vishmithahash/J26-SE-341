from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    EvidenceRequirement,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationIssue,
)


class CaseCategory(str, Enum):
    """Supported test case categories for Component 1 tool-call testing."""

    CORRECT_BEHAVIOUR = "CORRECT_BEHAVIOUR"
    WRONG_TOOL_SELECTION = "WRONG_TOOL_SELECTION"
    MISSING_ARGUMENTS = "MISSING_ARGUMENTS"
    MALFORMED_ARGUMENT_NAMES_OR_TYPES = "MALFORMED_ARGUMENT_NAMES_OR_TYPES"
    INCORRECT_ARGUMENT_VALUES = "INCORRECT_ARGUMENT_VALUES"
    CONTEXTUAL_SOURCE_MISMATCH = "CONTEXTUAL_SOURCE_MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class GenerationProvenance(BaseModel):
    """Provenance tracking how a test case was synthesized."""

    generator_id: str = Field(..., description="Generator implementation identifier")
    generator_version: str = Field(..., description="Version of the generator engine")
    seed: int | None = Field(
        default=None, description="Random/algorithmic seed used during synthesis"
    )
    rule_derivation: str = Field(
        ..., description="Description of the requirement and schema derivation logic"
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SyntheticRecordRequirement(BaseModel):
    """Specification of a synthetic record required in the test environment."""

    record_id: str = Field(
        ..., description="Identifier of the record in synthetic fixtures"
    )
    record_type: str = Field(
        ..., description="Entity type, e.g. 'order', 'customer', 'device'"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Concrete initial attributes for the record"
    )


class FixturePreparationPlan(BaseModel):
    """Plan describing required synthetic state before presenting the task to the agent."""

    fixture_capability_ref: str = Field(
        ..., description="Reference to the target fixture environment"
    )
    reset_hook_ref: str | None = Field(
        default=None, description="Reset capability identifier"
    )
    synthetic_records: list[SyntheticRecordRequirement] = Field(
        default_factory=list,
        description="Required synthetic records and initial values",
    )
    starting_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Environment starting flags (e.g. system balance, auth scope)",
    )
    declared_compatibility: bool = Field(
        default=True,
        description="Whether declared fixture supports the required records",
    )
    static_feasibility: bool = Field(
        default=True,
        description="Whether declared fixture plan is syntactically feasible",
    )
    runtime_readiness: bool = Field(
        default=False,
        description="Runtime environment readiness, strictly kept separate from static feasibility",
    )


class ExpectedToolCallSpec(BaseModel):
    """Expected tool-call constraints for a generated candidate case."""

    tool_name: str = Field(..., description="Expected or evaluated tool name")
    is_forbidden: bool = Field(
        default=False, description="Whether invocation of this tool is prohibited"
    )
    min_count: int = Field(default=1, ge=0, description="Minimum expected invocations")
    max_count: int | None = Field(
        default=1, ge=0, description="Maximum permitted invocations"
    )
    must_precede_tools: list[str] = Field(
        default_factory=list, description="Tools that must be preceded by this tool"
    )
    argument_constraints: list[ArgumentConstraint] = Field(
        default_factory=list, description="Argument presence and value constraints"
    )
    evidence_requirements: list[EvidenceRequirement] = Field(
        default_factory=list,
        description="Evidence channels required to verify this tool call",
    )


class GeneratedCandidateCase(BaseModel):
    """A generated candidate test case prior to deduplication and suite selection."""

    case_id: str = Field(..., description="Uniform case identifier")
    category: CaseCategory = Field(..., description="Case category")
    agent_task_prompt: str = Field(
        ..., description="Task instructions to present to the tested agent"
    )
    task_context_inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Public context inputs available to the agent (e.g. order_id, user query)",
    )
    requirement_refs: list[str] = Field(
        default_factory=list,
        description="IDs of task requirements justifying this case",
    )
    fixture_plan: FixturePreparationPlan = Field(
        ..., description="Synthetic data preparation plan"
    )
    expected_tool_calls: list[ExpectedToolCallSpec] = Field(
        default_factory=list,
        description="QA expectations: expected tool selections and argument constraints",
    )
    evidence_limitations: str | None = Field(
        default=None,
        description="Explicit limitation explanation when category is INSUFFICIENT_EVIDENCE",
    )
    provenance: GenerationProvenance = Field(
        ..., description="Generation provenance metadata"
    )
    canonical_hash: str = Field(
        default="", description="Semantic fingerprint used for deduplication"
    )
    validation_issues: list[ValidationIssue] = Field(
        default_factory=list, description="Validation issues detected on this candidate"
    )
    is_valid: bool = Field(
        default=True, description="True if no ERROR severity validation issues exist"
    )
    rejection_reason: str | None = Field(
        default=None, description="Reason if excluded from accepted suite"
    )


class AgentFacingTask(BaseModel):
    """Isolated task view presented to the tested agent.
    Strictly excludes QA expectations, oracle values, and validation results.
    """

    case_id: str = Field(..., description="Case identifier")
    task_prompt: str = Field(
        ..., description="User prompt or instructions for the agent"
    )
    context_inputs: dict[str, Any] = Field(
        default_factory=dict, description="Public context inputs provided to the agent"
    )
    permitted_tools: list[str] = Field(
        default_factory=list,
        description="Tools the agent is permitted to invoke for this task",
    )


class GenerationRequest(BaseModel):
    """Request payload to trigger automatic test case generation."""

    config_version: int = Field(
        default=1, ge=1, description="Target component configuration version"
    )
    requirement_ids: list[str] | None = Field(
        default=None,
        description="Specific requirement IDs to target. If None, targets all active requirements.",
    )
    tool_names: list[str] | None = Field(
        default=None,
        description="Specific tool names to target. If None, targets all declared tools.",
    )
    scenario_prompt: str | None = Field(
        default=None,
        description="Optional high-level user scenario prompt to guide generation",
    )
    case_categories: list[CaseCategory] = Field(
        default_factory=lambda: [
            CaseCategory.CORRECT_BEHAVIOUR,
            CaseCategory.WRONG_TOOL_SELECTION,
            CaseCategory.MISSING_ARGUMENTS,
            CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES,
            CaseCategory.INCORRECT_ARGUMENT_VALUES,
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
            CaseCategory.INSUFFICIENT_EVIDENCE,
        ],
        description="List of case categories to generate",
    )
    max_candidates: int = Field(
        default=20, ge=1, le=100, description="Maximum candidate cases to generate"
    )
    max_accepted_cases: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum cases to select for accepted suite",
    )
    seed: int | None = Field(
        default=None,
        description="Algorithmic seed for reproducible candidate synthesis",
    )
    generator_id: str = Field(
        default="c1_deterministic_generator",
        description="Identifier of the generator engine",
    )
    generator_version: str = Field(
        default="1.0.0", description="Version of the generator engine"
    )
    provider_settings: dict[str, Any] = Field(
        default_factory=dict, description="Provider/LLM configuration settings"
    )
    auto_promote_suite: bool = Field(
        default=False, description="Whether to automatically freeze accepted suite"
    )
    suite_id: str | None = Field(
        default=None, description="Suite identifier if auto-promoting"
    )
    suite_name: str | None = Field(
        default=None, description="Suite name if auto-promoting"
    )


class GenerationSummary(BaseModel):
    """Summary metrics of a generation run."""

    total_generated: int = Field(default=0)
    valid_candidates: int = Field(default=0)
    invalid_candidates: int = Field(default=0)
    duplicates_removed: int = Field(default=0)
    selected_count: int = Field(default=0)
    category_counts: dict[str, int] = Field(default_factory=dict)


class GenerationJobResponse(BaseModel):
    """Response contract representing a test generation run."""

    job_id: str
    project_id: str
    config_id: str
    config_version: int
    status: str
    content_hash: str
    summary: GenerationSummary
    suite_version_id: str | None = None
    created_at: datetime
