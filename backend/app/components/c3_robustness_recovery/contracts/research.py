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

    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    HELD_OUT_TEST = "HELD_OUT_TEST"
    TRAIN_DEV = "TRAIN_DEV"  # Retained for Phase 6 backward compatibility


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


class BlindedReviewerItem(BaseModel):
    """Anonymized, blinded trial record presented to an independent human reviewer."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(..., min_length=1, max_length=128)
    case_id: str = Field(..., min_length=1, max_length=128)
    project_id: str = Field(..., min_length=1, max_length=128)
    evidence_digest: str = Field(
        ..., description="Deterministic digest of reviewed evidence."
    )
    task_id: str
    tool_id: str
    observed_trace_summary: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Sanitized sequence of tool invocations, returns, and caller actions (without evaluator verdicts).",
    )
    caller_reported_outcome: str
    initial_state_observation: dict[str, Any] = Field(default_factory=dict)
    final_state_observation: dict[str, Any] = Field(default_factory=dict)
    contract_version: str = "1.0.0"
    permitted_terminal_outcomes: list[str] = Field(default_factory=list)
    max_retries_allowed: int | None = None
    evidence_sufficient: bool = True


class BlindedReviewerPacket(BaseModel):
    """Export packet containing blinded trial items for independent human review."""

    model_config = ConfigDict(extra="forbid")

    packet_id: str = Field(..., min_length=1, max_length=128)
    project_id: str = Field(..., min_length=1, max_length=128)
    experiment_id: str = Field(..., min_length=1, max_length=128)
    protocol_version: str = Field(default="2.0.0")
    total_cases: int = Field(default=0, ge=0)
    created_at_utc: str
    items: list[BlindedReviewerItem] = Field(default_factory=list)


class IndependentReviewerLabel(BaseModel):
    """Explicitly attributed label authored by an independent reviewer."""

    model_config = ConfigDict(extra="forbid")

    label_id: str = Field(..., min_length=1, max_length=128)
    reviewer_id: str = Field(
        ..., min_length=1, max_length=64, description="E.g. REV_A, REV_B"
    )
    pair_id: str = Field(..., min_length=1, max_length=128)
    case_id: str = Field(..., min_length=1, max_length=128)
    project_id: str = Field(..., min_length=1, max_length=128)
    evidence_digest: str = Field(
        ..., description="Digest of verified evidence reviewed."
    )
    contract_version: str = Field(default="1.0.0")
    permitted_outcome_observed: bool
    defect_present: bool = Field(
        ..., description="Whether a failure recovery defect was present."
    )
    assigned_verdict: RecoveryVerdict | None = None
    violation_type: str | None = None
    first_observable_violation: str | None = None
    evidence_sufficient: bool = True
    reviewer_provenance: ReviewerProvenance = ReviewerProvenance.INDEPENDENT_EXPERT
    notes: str | None = None
    label_version: str = Field(default="1.0.0")
    created_at_utc: str


class MetricScore(BaseModel):
    """Pure research metric score with explicit numerator and denominator."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    numerator: int | None = None
    denominator: int | None = None
    denominator_unit: str = Field(..., description="Explicit unit of the denominator.")
    is_defined: bool = True
    undefined_reason: str | None = None


class InterReviewerAgreementResult(BaseModel):
    """Inter-rater reliability analysis between two independent reviewers prior to reconciliation."""

    model_config = ConfigDict(extra="forbid")

    reviewer_a_id: str
    reviewer_b_id: str
    total_pairs_compared: int
    concordant_pairs_count: int
    discordant_pairs_count: int
    percentage_agreement: MetricScore
    cohens_kappa: MetricScore
    disputed_pair_ids: list[str] = Field(default_factory=list)
    reconciliation_required: bool = False


class ReconciliationRecord(BaseModel):
    """Audit record capturing dispute reconciliation without modifying original independent labels."""

    model_config = ConfigDict(extra="forbid")

    reconciliation_id: str = Field(..., min_length=1, max_length=128)
    pair_id: str = Field(..., min_length=1, max_length=128)
    case_id: str = Field(..., min_length=1, max_length=128)
    adjudicator_id: str = Field(..., min_length=1, max_length=64)
    reviewer_a_id: str
    reviewer_b_id: str
    reviewer_a_label_id: str
    reviewer_b_label_id: str
    adjudicated_verdict: RecoveryVerdict
    adjudicated_defect_present: bool
    adjudication_rationale: str
    adjudicated_at_utc: str


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


class MulticlassConfusionMatrix(BaseModel):
    """4-way multiclass confusion matrix (PASS_COMPLETED, PASS_GRACEFUL, FAIL, INCONCLUSIVE)."""

    model_config = ConfigDict(extra="forbid")

    classes: list[str] = Field(
        default_factory=lambda: [
            RecoveryVerdict.PASS_COMPLETED.value,
            RecoveryVerdict.PASS_GRACEFUL.value,
            RecoveryVerdict.FAIL.value,
            RecoveryVerdict.INCONCLUSIVE.value,
        ]
    )
    matrix: dict[str, dict[str, int]] = Field(default_factory=dict)
    total_samples: int = 0
    accuracy: MetricScore
    per_class_precision: dict[str, MetricScore] = Field(default_factory=dict)
    per_class_recall: dict[str, MetricScore] = Field(default_factory=dict)
    per_class_f1: dict[str, MetricScore] = Field(default_factory=dict)
    macro_f1: MetricScore


class CleanToFaultOutcomeTransitions(BaseModel):
    """Transitions from baseline clean control to fault-injected trial outcomes."""

    model_config = ConfigDict(extra="forbid")

    clean_pass_to_fault_recovered: int = 0
    clean_pass_to_fault_defect: int = 0
    clean_pass_to_fault_inconclusive: int = 0
    clean_disqualified_count: int = 0
    total_matched_pairs: int = 0


class BootstrapConfidenceInterval(BaseModel):
    """Deterministic cluster bootstrap confidence interval grouped by case family."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str
    point_estimate: float | None
    ci_lower: float | None = None
    ci_upper: float | None = None
    confidence_level: float = 0.95
    n_bootstraps: int = 1000
    n_clusters: int = 0
    is_valid: bool = True
    limitation: str | None = None


class FixedSuiteComparisonResult(BaseModel):
    """Comparative outcome between fixed hand-crafted test suite and automatic generation under matched budgets."""

    model_config = ConfigDict(extra="forbid")

    fixed_cases_count: int
    generated_cases_count: int
    fixed_validity_rate: MetricScore
    generated_validity_rate: MetricScore
    fixed_feasible_coverage: MetricScore
    generated_feasible_coverage: MetricScore
    budget_equivalent: bool = True
    notes: str = ""


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
    val_families_count: int = 0

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

    # Phase 7 Multiclass, Transition & Statistical Extensions
    multiclass_confusion_matrix: MulticlassConfusionMatrix | None = None
    outcome_transitions: CleanToFaultOutcomeTransitions | None = None
    execution_overheads: dict[str, MetricScore] = Field(default_factory=dict)
    bootstrap_ci: BootstrapConfidenceInterval | None = None

    # Comparative Setup
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3
    ablation_type: AblationType = AblationType.NONE

    # Transparency & Limitations
    demonstration_mode: bool = True
    limitations: list[str] = Field(default_factory=list)
