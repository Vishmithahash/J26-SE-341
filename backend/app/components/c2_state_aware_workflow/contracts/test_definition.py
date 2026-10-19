"""Generated test definition contract for C2.

Prepares the data structures for Day 2 test generation:
pinned model version/hash, category, task, fixture, seed, private reference paths,
expected outcome, mutation provenance, readiness, and diagnostics.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MutationType(str, Enum):
    SKIPPED_STEP = "skipped_step"
    REORDERED_STEP = "reordered_step"
    REPEATED_STEP = "repeated_step"
    ILLEGAL_TRANSITION = "illegal_transition"
    WRONG_ENTITY = "wrong_entity"
    MISSING_EFFECT = "missing_effect"
    UNEXPECTED_PROTECTED_STATE_CHANGE = "unexpected_protected_state_change"
    PREMATURE_TERMINATION = "premature_termination"


class MutationProvenance(BaseModel):
    """Metadata regarding how a workflow was mutated for fault sensitivity testing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mutation_type: MutationType
    parent_case_id: str | None = None
    target_step_index: int | None = None
    target_transition_id: str | None = None
    description: str
    targeted_rule: str | None = None
    changed_details: dict[str, Any] = Field(default_factory=dict)
    intended_violation: str | None = None
    injected_fault_code: str | None = None
    is_ambiguous_or_non_discriminating: bool = False
    ambiguity_reason: str | None = None


class ExecutionMode(str, Enum):
    LIVE_AGENT = "live_agent"
    SYNTHETIC_EVALUATOR = "synthetic_evaluator"


class TestCategory(str, Enum):
    __test__ = False
    VALID = "valid"
    ALTERNATIVE = "alternative"
    NEGATIVE = "negative"
    MUTATED = "mutated"


class ExpectedOutcomeType(str, Enum):
    PASS = "PASS"
    EXPECTED_REJECTION_PASS = "EXPECTED REJECTION PASS"


class TestReadinessStatus(str, Enum):
    __test__ = False
    TEST_READY = "TEST_READY"
    TEST_NOT_READY = "TEST_NOT_READY"


class GeneratedTestDefinition(BaseModel):
    """Contract for an executable workflow test generated from an approved EFSM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    test_id: str
    project_id: str
    suite_id: str | None = None
    pinned_model_id: str
    pinned_model_version: str
    model_content_hash: str
    generator_version: str = "c2_generator_v1"

    category: TestCategory
    execution_mode: ExecutionMode = ExecutionMode.LIVE_AGENT
    task: str = Field(
        ..., description="Natural language prompt for the agent under test"
    )
    permitted_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Allowlisted context permitted to be shared with the agent",
    )
    fixture_ref: str = Field(
        ..., description="Fixture ID or URI to be reset before execution"
    )
    fixture_version: str = "1.0.0"
    seed: int | None = None

    # Input parameters / variable bindings snapshot
    input_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of initial domain inputs and bound variables",
    )

    # Hidden from the tested agent during execution (strictly evaluator private)
    private_reference_paths: list[list[str]] = Field(
        default_factory=list,
        description="List of valid state sequences representing reference solution paths",
    )
    private_reference_transitions: list[list[str]] = Field(
        default_factory=list,
        description="List of transition ID sequences representing reference paths",
    )
    private_reference_assertions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Assertions on expected effects, entity continuity, and protected state",
    )
    expected_outcome: ExpectedOutcomeType
    mutation_provenance: MutationProvenance | None = None

    planned_coverage_targets: list[str] = Field(
        default_factory=list,
        description="Model transitions or guards targeted by this test case",
    )

    readiness: TestReadinessStatus = TestReadinessStatus.TEST_READY
    readiness_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GenerateTestSuiteRequest(BaseModel):
    """Configuration options for automatic workflow test suite generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    version: str
    generator_version: str = "c2_generator_v1"
    seed: int = 42
    max_depth: int = 15
    max_loop_visits: int = 1
    case_budget: int = 20
    include_alternatives: bool = True
    include_negative_rejections: bool = True
    include_mutations: bool = True
    mutation_budget: int = 8
    enabled_mutation_types: list[MutationType] | None = None
    fixture_ref: str | None = None


class TestSuiteDiagnostics(BaseModel):
    """Diagnostics and planned coverage summary of the generation run."""

    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    generator_version: str = "c2_generator_v1"
    seed: int
    paths_explored: int = 0
    depth_limit_reached: bool = False
    cases_generated_count: int = 0
    cases_deduplicated_count: int = 0
    infeasible_targets_count: int = 0
    unresolved_constraints: list[str] = Field(default_factory=list)
    generation_limits_hit: list[str] = Field(default_factory=list)
    readiness_breakdown: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    planned_transition_coverage: dict[str, Any] = Field(default_factory=dict)
    planned_guard_coverage: dict[str, Any] = Field(default_factory=dict)


class GeneratedTestSuite(BaseModel):
    """Complete generated test suite for an approved EFSM model version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    suite_id: str
    project_id: str
    pinned_model_id: str
    pinned_model_version: str
    model_content_hash: str
    generator_version: str = "c2_generator_v1"
    seed: int
    config: dict[str, Any] = Field(default_factory=dict)
    cases: list[GeneratedTestDefinition] = Field(default_factory=list)
    diagnostics: TestSuiteDiagnostics
    total_cases: int = 0
    ready_cases_count: int = 0
    not_ready_cases_count: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentTaskPayload(BaseModel):
    """Strictly allowlisted task payload intended for the agent under test.

    Excludes reference paths, expected outcomes, assertions, mutation labels,
    and intended divergence locations to maintain oracle isolation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: str
    project_id: str
    task: str
    fixture_ref: str
    permitted_context: dict[str, Any] = Field(default_factory=dict)


class QASuiteExport(BaseModel):
    """Full QA suite export containing complete metadata, assertions, and reference oracles."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    suite_id: str
    project_id: str
    model_id: str
    model_version: str
    model_content_hash: str
    generator_version: str
    seed: int
    created_at: datetime
    diagnostics: TestSuiteDiagnostics
    cases: list[GeneratedTestDefinition]
