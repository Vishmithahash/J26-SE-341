"""C2 report contribution contracts for multi-component QA integration.

Defines the typed schemas for per-run C2 report contributions and suite summaries,
recording execution provenance, honest readiness limitations, divergence localisation
uncertainty, exact denominators for observed coverage, and publishing adapter status.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.contracts.coverage import (
    DetailedObservedCoverage,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    FirstDivergenceDetail,
    RuntimeVerdict,
    ViolationDetail,
)


class ExecutionProvenance(BaseModel):
    """Detailed provenance distinguishing intended execution mode from actual execution origin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intended_execution_mode: str = Field(
        ...,
        description="Mode intended by the test case definition, e.g. 'live_agent' or 'synthetic_demonstration'",
    )
    actual_execution_origin: str = Field(
        ...,
        description="Actual execution origin: 'live_agent_run', 'scripted_synthetic_demonstration', or 'controlled_trace_fixture'",
    )
    runner_id: str = Field(
        ..., description="Identifier of the executing runner/adapter"
    )
    runner_version: str = "2026.1"
    is_live_execution: bool = False
    observation_capabilities: list[str] = Field(
        default_factory=lambda: [
            "state_snapshots",
            "before_after_diffs",
            "event_logs",
        ]
    )
    live_capabilities_available: bool = False
    unavailable_live_capabilities: list[str] = Field(default_factory=list)


class C2ReportContributionContract(BaseModel):
    """Versioned report contribution representing C2's findings for a single workflow run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component: str = "C2_STATE_AWARE_WORKFLOW"
    contract_version: str = "2026.1"

    project_id: str
    suite_id: str
    test_id: str
    run_id: str
    evaluation_id: str

    model_id: str
    model_version: str
    model_content_hash: str

    fixture_version: str = "2026.1"
    runner_version: str = "2026.1"
    evaluator_version: str = "c2_evaluator_v1"

    execution_provenance: ExecutionProvenance

    verdict: RuntimeVerdict
    verdict_category: str = Field(
        ...,
        description="'EVALUATION_OUTCOME' for scored runs vs 'READINESS_REJECTION' for pre-flight errors",
    )
    reason_codes: list[str] = Field(default_factory=list)

    expected_states: list[str] = Field(default_factory=list)
    observed_states: list[str] = Field(default_factory=list)
    accepted_alternatives: list[str] = Field(default_factory=list)
    violated_rules: list[ViolationDetail] = Field(default_factory=list)

    first_divergence: FirstDivergenceDetail | None = None
    divergence_localisation_uncertainty: str | None = None

    evidence_digest: str = Field(
        ..., description="Canonical SHA-256 digest of original retained evidence"
    )
    evidence_references: list[str] = Field(default_factory=list)

    observed_coverage: DetailedObservedCoverage

    readiness_limitations: list[str] = Field(default_factory=list)
    observation_limitations: list[str] = Field(default_factory=list)

    evaluator_timing_ms: float = 0.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    published_to_shared_aggregator: bool = False
    publishing_status: str = "STUB_PENDING_SHARED_AGGREGATOR"


class C2SuiteReportContract(BaseModel):
    """Aggregated C2 report for an entire test suite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component: str = "C2_STATE_AWARE_WORKFLOW"
    contract_version: str = "2026.1"

    project_id: str
    suite_id: str
    model_id: str
    model_version: str
    model_content_hash: str

    total_cases: int = 0
    evaluated_cases: int = 0

    verdict_counts: dict[str, int] = Field(
        default_factory=lambda: {v.value: 0 for v in RuntimeVerdict}
    )
    readiness_rejection_counts: dict[str, int] = Field(default_factory=dict)
    scored_agent_outcomes: dict[str, int] = Field(default_factory=dict)

    aggregate_observed_coverage: DetailedObservedCoverage
    case_reports: list[C2ReportContributionContract] = Field(default_factory=list)

    published_to_shared_aggregator: bool = False
    publishing_status: str = "STUB_PENDING_SHARED_AGGREGATOR"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
