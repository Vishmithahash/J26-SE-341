"""Generated test definition contract for C2.

Prepares the data structures for Day 2 test generation:
pinned model version/hash, category, task, fixture, seed, private reference paths,
expected outcome, mutation provenance, and readiness.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MutationType(str, Enum):
    SKIPPED_STEP = "skipped_step"
    REORDERED_STEP = "reordered_step"
    REPEATED_STEP = "repeated_step"
    ILLEGAL_TRANSITION = "illegal_transition"
    WRONG_ENTITY = "wrong_entity"
    MISSING_EFFECT = "missing_effect"


class MutationProvenance(BaseModel):
    """Metadata regarding how a workflow was mutated for fault sensitivity testing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mutation_type: MutationType
    target_step_index: int | None = None
    target_transition_id: str | None = None
    description: str
    injected_fault_code: str | None = None


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
    pinned_model_id: str
    pinned_model_version: str
    model_content_hash: str

    category: TestCategory
    task: str = Field(
        ..., description="Natural language prompt for the agent under test"
    )
    fixture_ref: str = Field(
        ..., description="Fixture ID or URI to be reset before execution"
    )
    seed: int | None = None

    # Hidden from the tested agent during execution
    private_reference_paths: list[list[str]] = Field(
        default_factory=list,
        description="List of valid state sequences representing reference solution paths",
    )
    expected_outcome: ExpectedOutcomeType
    mutation_provenance: MutationProvenance | None = None

    readiness: TestReadinessStatus = TestReadinessStatus.TEST_READY
    readiness_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
