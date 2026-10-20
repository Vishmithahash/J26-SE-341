"""Contracts for C2 experiments, baseline evaluations, ground-truth labels, and research metrics."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.contracts.baseline import (
    BaselinePredictionContract,
    BaselineType,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.report import (
    ExecutionProvenance,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)


class DatasetPartition(str, Enum):
    """Partition split for machine learning / empirical software engineering evaluation."""

    DEVELOPMENT = "DEVELOPMENT"
    HELD_OUT = "HELD_OUT"
    ALL_CASES = "ALL_CASES"


class ReviewStatus(str, Enum):
    """Review and verification status of ground-truth labels."""

    DEVELOPER_FIXTURE = "DEVELOPER_FIXTURE"
    UNREVIEWED_INTENDED_MUTATION = "UNREVIEWED_INTENDED_MUTATION"
    REVIEWABLE_TEMPLATE = "REVIEWABLE_TEMPLATE"
    INDEPENDENTLY_REVIEWED = "INDEPENDENTLY_REVIEWED"
    PENDING_REVIEW = "PENDING_REVIEW"


class MutationFamily(str, Enum):
    """Classification of workflow mutation and failure types."""

    NONE = "NONE"
    STATE_EFFECT_CORRUPTION = "STATE_EFFECT_CORRUPTION"
    SKIPPED_INTERMEDIATE_ACTION = "SKIPPED_INTERMEDIATE_ACTION"
    OUT_OF_ORDER_ACTION = "OUT_OF_ORDER_ACTION"
    PREMATURE_TERMINATION = "PREMATURE_TERMINATION"
    UNAUTHORIZED_BYPASS = "UNAUTHORIZED_BYPASS"
    INVALID_ARGUMENT_CALL = "INVALID_ARGUMENT_CALL"
    STALE_SNAPSHOT_REPLAY = "STALE_SNAPSHOT_REPLAY"


class GroundTruthLabel(BaseModel):
    """Separated ground-truth label for an execution case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_workflow_violation: bool  # Positive class for binary detection: True = violation, False = conforming
    expected_verdict: RuntimeVerdict
    is_valid_test: bool = (
        True  # Generated-test validity: was the test feasible and valid?
    )
    has_state_effect_fault: bool = False
    mutation_family: MutationFamily = MutationFamily.NONE

    ground_truth_divergence_event_id: str | None = None
    ground_truth_divergence_step: int | None = None
    ground_truth_divergence_location_known: bool = False

    review_status: ReviewStatus = ReviewStatus.DEVELOPER_FIXTURE
    reviewer_name: str | None = None
    reviewer_notes: str | None = None
    label_provenance: str = "SYNTHETIC_DEVELOPER_FIXTURE"


class ExperimentCaseRecord(BaseModel):
    """A single frozen case within a versioned experiment dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    parent_case_id: str | None = None  # Prevents child leakage across partitions
    domain: str  # e.g. "ECOMMERCE", "FLIGHT_BOOKING", "LMS"
    workflow_name: str

    model_id: str
    model_version: str
    test_id: str
    test_version: str
    fixture_id: str
    fixture_digest: str
    evidence_id: str
    evidence_digest: str

    execution_provenance: ExecutionProvenance
    partition: DatasetPartition
    ground_truth: GroundTruthLabel

    # Retained evidence and fixture for self-contained independent replay
    frozen_evidence: RuntimeEvidenceContract | None = None
    frozen_fixture: dict[str, Any] | None = None


class ExperimentDatasetManifest(BaseModel):
    """Versioned and frozen dataset manifest for reproducible baseline comparisons."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    name: str
    version: str
    description: str = ""
    project_id: str

    is_frozen: bool = False
    frozen_at: datetime | None = None
    manifest_digest: str = ""

    cases: list[ExperimentCaseRecord] = Field(default_factory=list)
    case_count: int = 0
    development_count: int = 0
    held_out_count: int = 0


class ExperimentCaseMethodResult(BaseModel):
    """Record of a single baseline method prediction on a dataset case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    method_id: BaselineType
    partition: DatasetPartition
    prediction: BaselinePredictionContract
    is_excluded: bool = False
    exclusion_reason: str | None = None


class BinaryClassificationMetrics(BaseModel):
    """Binary detection metrics where workflow violations are the positive class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    inconclusive_count: int = 0
    excluded_count: int = 0
    total_evaluated: int = 0

    precision: float | None = None
    precision_status: str = "CALCULATED"
    recall: float | None = None
    recall_status: str = "CALCULATED"
    f1_score: float | None = None
    f1_status: str = "CALCULATED"

    mutation_detection_score: float | None = None
    mutation_detection_status: str = "CALCULATED"
    state_effect_fault_detection_score: float | None = None
    state_effect_fault_detection_status: str = "CALCULATED"

    inconclusive_rate: float | None = None
    inconclusive_rate_status: str = "CALCULATED"


class DivergenceLocalizationMetrics(BaseModel):
    """First-proven-divergence localization metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    can_localize: bool
    applicable_cases_with_known_location: int = 0
    exact_matches: int = 0
    missed_or_unlocalized: int = 0
    accuracy: float | None = None
    accuracy_status: str = "CALCULATED"
    cases_with_unknown_location_excluded: int = 0


class MethodResearchMetrics(BaseModel):
    """Comprehensive research metrics for an evaluation method on a dataset partition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method_id: BaselineType
    method_name: str
    partition: DatasetPartition
    sample_count: int = 0

    detection_metrics: BinaryClassificationMetrics
    localization_metrics: DivergenceLocalizationMetrics

    # Overhead measurements
    overhead_median_ms: float = 0.0
    overhead_p95_ms: float = 0.0

    # Coverage metrics (when applicable, e.g. B4)
    transition_coverage: float | None = None
    guard_outcome_coverage: float | None = None
    selected_path_coverage: float | None = None
    state_effect_coverage: float | None = None
    detailed_coverage: Any = None
    detailed_coverage_by_model: dict[str, Any] | None = None


class ExperimentComparisonReport(BaseModel):
    """Full research baseline comparison report containing metrics across B1-B4."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    experiment_name: str
    dataset_id: str
    dataset_version: str
    project_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    generated_test_validity_rate: float | None = None
    generated_test_validity_status: str = "CALCULATED"
    valid_test_count: int = 0
    total_test_count: int = 0

    metrics_by_partition: dict[str, dict[str, MethodResearchMetrics]] = Field(
        default_factory=dict
    )
    metrics_by_method: dict[str, MethodResearchMetrics] = Field(default_factory=dict)
    metrics_by_domain: dict[str, dict[str, BinaryClassificationMetrics]] = Field(
        default_factory=dict
    )
    metrics_by_mutation: dict[str, dict[str, BinaryClassificationMetrics]] = Field(
        default_factory=dict
    )
    metrics_by_provenance: dict[str, dict[str, BinaryClassificationMetrics]] = Field(
        default_factory=dict
    )

    acceptance_criteria_results: dict[str, bool] = Field(default_factory=dict)
    acceptance_criteria_by_method: dict[str, dict[str, bool | None]] = Field(
        default_factory=dict
    )
    acceptance_notes_by_method: dict[str, list[str]] = Field(default_factory=dict)
    acceptance_notes: list[str] = Field(default_factory=list)
