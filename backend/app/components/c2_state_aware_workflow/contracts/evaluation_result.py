"""Evaluation result contract for C2.

Prepares the data structures for Day 2 trace conformance evaluation.
Defines exactly the six runtime verdicts specified in the research proposal:
- PASS
- EXPECTED REJECTION PASS
- FAIL
- INCONCLUSIVE
- MODEL NOT READY
- TEST NOT READY
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeVerdict(str, Enum):
    PASS = "PASS"
    EXPECTED_REJECTION_PASS = "EXPECTED REJECTION PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    MODEL_NOT_READY = "MODEL NOT READY"
    TEST_NOT_READY = "TEST NOT READY"


class ViolationType(str, Enum):
    INVALID_TRANSITION = "INVALID_TRANSITION"
    GUARD_VIOLATION = "GUARD_VIOLATION"
    INVARIANT_BROKEN = "INVARIANT_BROKEN"
    ENTITY_MISMATCH = "ENTITY_MISMATCH"
    MISSING_EFFECT = "MISSING_EFFECT"
    OUTCOME_MISMATCH = "OUTCOME_MISMATCH"
    PROTECTED_FIELD_MUTATED = "PROTECTED_FIELD_MUTATED"
    PREMATURE_TERMINATION = "PREMATURE_TERMINATION"


class ViolationDetail(BaseModel):
    """Detailed record of a single workflow rule or state violation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_type: ViolationType
    event_index: int | None = None
    event_id: str | None = None
    source_state: str | None = None
    rule_reference: str | None = None
    message: str
    expected: Any = None
    observed: Any = None


class FirstDivergenceDetail(BaseModel):
    """Localisation of the earliest step at which the trace deviated from valid model paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_index: int = Field(
        ..., ge=0, description="Earliest event index i where conformance failed"
    )
    event_id: str | None = None
    state_at_divergence: str
    attempted_event: str
    reason: str
    violation_type: ViolationType | None = None
    expected_alternatives: list[str] = Field(default_factory=list)
    evidence_excerpt: dict[str, Any] = Field(default_factory=dict)


class WorkflowCoverageSummary(BaseModel):
    """Summary of model elements exercised during test execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transitions_total: int = 0
    transitions_covered: int = 0
    transition_coverage_ratio: float = 0.0

    guards_total: int = 0
    guards_covered: int = 0
    guard_coverage_ratio: float = 0.0

    milestones_total: int = 0
    milestones_reached: int = 0
    milestone_coverage_ratio: float = 0.0


class EvaluationResultContract(BaseModel):
    """Complete evaluation report for a test run against a pinned EFSM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    evaluation_id: str | None = None
    project_id: str | None = None
    suite_id: str | None = None
    run_id: str | None = None
    evaluator_version: str = "c2_evaluator_v1"

    verdict: RuntimeVerdict
    reasons: list[str] = Field(default_factory=list)

    model_id: str
    model_version: str
    model_content_hash: str
    test_id: str
    test_version: str | None = None
    fixture_version: str | None = None

    expected_states: list[str] = Field(default_factory=list)
    observed_states: list[str] = Field(default_factory=list)
    violations: list[ViolationDetail] = Field(default_factory=list)
    first_divergence: FirstDivergenceDetail | None = None
    evidence_references: list[str] = Field(default_factory=list)
    coverage: WorkflowCoverageSummary = Field(default_factory=WorkflowCoverageSummary)
    evaluator_timing_ms: float = 0.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
