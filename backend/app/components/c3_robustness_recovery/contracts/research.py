"""Research contracts for Component 3 Phase 6: Robustness and Recovery Research Validation.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    RecoveryVerdictCounts,
)


class DatasetSplit(StrEnum):
    """Dataset partition for research evaluation."""

    TRAIN_DEV = "TRAIN_DEV"
    HELD_OUT_TEST = "HELD_OUT_TEST"


class ReviewerProvenance(StrEnum):
    """Provenance category for reference recovery labels."""

    INDEPENDENT_EXPERT = "INDEPENDENT_EXPERT"
    EXTERNAL_AUDITOR = "EXTERNAL_AUDITOR"
    SYNTHETIC_FIXTURE_LABEL = "SYNTHETIC_FIXTURE_LABEL"


class AdjudicationStatus(StrEnum):
    """Reviewer agreement or adjudication state."""

    UNCONTESTED = "UNCONTESTED"
    ADJUDICATED = "ADJUDICATED"
    DISPUTED = "DISPUTED"


class BaselineType(StrEnum):
    """Comparative evaluation baseline types."""

    PRODUCTION_C3 = "PRODUCTION_C3"
    FIXED_SUITE_BASELINE = "FIXED_SUITE_BASELINE"
    OUTCOME_ONLY_BASELINE = "OUTCOME_ONLY_BASELINE"


class AblationType(StrEnum):
    """Evaluator and generation ablation variants."""

    NONE = "NONE"
    NO_CAPABILITY_VALIDATION = "NO_CAPABILITY_VALIDATION"
    NO_EXPOSURE_RECEIPTS = "NO_EXPOSURE_RECEIPTS"
    NO_STATE_FACTS = "NO_STATE_FACTS"
    NO_EFFECT_PHASE = "NO_EFFECT_PHASE"


class ReviewerLabelRecord(BaseModel):
    """Independent ground-truth label for a trial pair evidence record."""

    model_config = ConfigDict(extra="forbid")

    label_id: str = Field(..., min_length=1, max_length=128)
    label_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    pair_id: str = Field(..., min_length=1, max_length=128)
    case_id: str = Field(..., min_length=1, max_length=128)
    project_id: str = Field(..., min_length=1, max_length=128)

    expected_verdict: RecoveryVerdict | None = None
    defect_present: bool = Field(
        ..., description="Whether a failure recovery defect was present in the trial."
    )
    defect_type: str | None = Field(
        None,
        description="Optional defect categorization (e.g. UNVERIFIED_COMMIT_RETRY).",
    )

    reviewer_provenance: ReviewerProvenance
    reviewer_id: str | None = Field(
        None, description="Anonymized or documented reviewer identifier."
    )
    adjudication_status: AdjudicationStatus = AdjudicationStatus.UNCONTESTED
    notes: str | None = None
    evidence_digest: str | None = Field(
        None, description="Digest of the evidence artifact reviewed."
    )
    created_at_utc: str


class ExperimentBudgets(BaseModel):
    """Enforced resource and duration bounds for reproducible experiments."""

    model_config = ConfigDict(extra="forbid")

    max_case_timeout_sec: float = Field(default=10.0, ge=1.0, le=300.0)
    max_suite_timeout_sec: float = Field(default=60.0, ge=1.0, le=3600.0)
    max_tool_calls_budget: int = Field(default=10, ge=1, le=100)
    max_cases: int = Field(default=20, ge=1, le=200)


class ExperimentManifest(BaseModel):
    """Immutable, versioned research protocol manifest."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(..., min_length=1, max_length=128)
    version: str = Field(default="1.0.0", min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)

    target_domains: list[str] = Field(min_length=1, max_length=10)
    adapter_declarations: dict[str, str] = Field(
        ..., description="Mapping of adapter_id to adapter_version."
    )
    family_splits: dict[str, DatasetSplit] = Field(
        ..., description="Strict partition mapping case_family_id to DatasetSplit."
    )

    generation_seed: int = 42
    selection_seed: int = 42
    repetition_seeds: list[int] = Field(default_factory=lambda: [42, 43, 44])
    repetitions_per_case: int = Field(default=3, ge=1, le=10)

    budgets: ExperimentBudgets = Field(default_factory=ExperimentBudgets)
    evaluator_version: str = Field(default="1.2.0")
    rule_set_version: str = Field(default="1.2.0")
    created_at_utc: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfusionMatrix(BaseModel):
    """Binary defect classification confusion matrix."""

    model_config = ConfigDict(extra="forbid")

    true_positives: int = 0  # Reference defect=True AND Evaluator FAIL
    false_positives: int = 0  # Reference defect=False AND Evaluator FAIL
    true_negatives: int = (
        0  # Reference defect=False AND Evaluator PASS (COMPLETED or GRACEFUL)
    )
    false_negatives: int = 0  # Reference defect=True AND Evaluator PASS (False Pass!)
    inconclusive_count: int = 0  # Evaluator INCONCLUSIVE
    unscored_count: int = 0  # Ineligible, unconfirmed exposure, or unscored


class MetricScore(BaseModel):
    """Pure research metric score with explicit numerator and denominator."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    numerator: int | None = None
    denominator: int | None = None
    denominator_unit: str = Field(..., description="Explicit unit of the denominator.")
    is_defined: bool = True
    undefined_reason: str | None = None


class ResearchMetricsReport(BaseModel):
    """Comprehensive research validation and metrics report."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    evaluator_version: str
    rule_set_version: str
    target_domains: list[str]
    provenance_mode: str  # DEMONSTRATION or LIVE
    generated_at_utc: str

    # Case & Family Accounting
    total_case_families: int
    dev_families_count: int
    test_families_count: int

    planned_cases_count: int
    executed_pairs_count: int
    evaluated_trials_count: int

    blocked_cases_count: int
    unsupported_cases_count: int
    cancelled_cases_count: int
    error_cases_count: int

    # Clean Control & Exposure Rates
    clean_qualified_count: int
    clean_disqualified_count: int
    clean_indeterminate_count: int
    clean_qualification_rate: MetricScore

    confirmed_exposure_count: int
    not_triggered_exposure_count: int
    unknown_exposure_count: int
    exposure_rate: MetricScore

    # Verdict Breakdown
    verdict_breakdown: RecoveryVerdictCounts

    # Independent Labeled Accuracy Metrics (None if no labels available)
    labeled_trials_count: int = 0
    unlabeled_trials_count: int = 0
    confusion_matrix: ConfusionMatrix | None = None

    accuracy: MetricScore | None = None
    precision: MetricScore | None = None
    recall: MetricScore | None = None
    f1_score: MetricScore | None = None
    false_pass_rate: MetricScore | None = None
    abstention_rate: MetricScore | None = None

    # Comparative Setup
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3
    ablation_type: AblationType = AblationType.NONE

    # Transparency & Limitations
    demonstration_mode: bool = True
    limitations: list[str] = Field(default_factory=list)
