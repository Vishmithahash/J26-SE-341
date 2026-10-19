"""Observed workflow coverage contracts for C2.

Specifies typed structures for transition coverage, guard-outcome coverage,
selected-path coverage, and state-effect coverage with explicit numerators,
denominators, target identifiers, and evidence references.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricCoverageDetail(BaseModel):
    """Detailed breakdown for an individual coverage metric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    numerator: int = Field(..., ge=0, description="Covered target count")
    denominator: int = Field(..., ge=0, description="Total target count")
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    target_identifiers: list[str] = Field(default_factory=list)
    covered_targets: list[str] = Field(default_factory=list)
    uncovered_targets: list[str] = Field(default_factory=list)
    unknown_or_ambiguous_observations: list[str] = Field(default_factory=list)
    proven_infeasible_targets: list[dict[str, Any]] = Field(default_factory=list)
    supporting_evidence_references: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of target ID to supporting event IDs or trace references",
    )


class TransitionCoverageDetail(MetricCoverageDetail):
    """Unique transition IDs established by execution evidence divided by defined coverage targets."""

    metric_name: str = "transition_coverage"


class GuardOutcomeCoverageDetail(MetricCoverageDetail):
    """Tracks each declared guard's TRUE and FALSE outcome targets separately."""

    metric_name: str = "guard_outcome_coverage"
    total_guards_defined: int = 0
    total_outcome_targets: int = 0
    guards_encountered_count: int = 0
    guards_true_count: int = 0
    guards_false_count: int = 0
    guards_unknown_count: int = 0
    repeated_observations_deduplicated: bool = True


class SelectedPathCoverageDetail(MetricCoverageDetail):
    """Completed selected normal, alternative, and rejection paths from an explicit target catalogue."""

    metric_name: str = "selected_path_coverage"
    total_catalogue_paths: int = 0
    completed_paths: list[str] = Field(default_factory=list)
    uncovered_paths: list[str] = Field(default_factory=list)


class StateEffectCoverageDetail(MetricCoverageDetail):
    """Declared effect obligations checked with sufficient observations."""

    metric_name: str = "state_effect_coverage"
    total_effects_defined: int = 0
    satisfied_checks: list[str] = Field(default_factory=list)
    violated_checks: list[str] = Field(default_factory=list)
    unknown_checks: list[str] = Field(default_factory=list)
    effect_check_ratio: float = 0.0
    fault_detection_accuracy: float = 1.0


class DetailedObservedCoverage(BaseModel):
    """Complete observed coverage report for a run or aggregate suite against a pinned EFSM model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    model_version: str
    model_content_hash: str
    transition_coverage: TransitionCoverageDetail
    guard_outcome_coverage: GuardOutcomeCoverageDetail
    selected_path_coverage: SelectedPathCoverageDetail
    state_effect_coverage: StateEffectCoverageDetail
    overall_observed_coverage_ratio: float = 0.0
    aggregation_basis: str = "exact_pinned_model_targets_v1"
