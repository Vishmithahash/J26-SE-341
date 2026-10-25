"""Contracts and typed schemas for Phase 6 research evaluation tooling.

Includes versioned evaluation datasets, reviewer packets, inter-rater agreement (Cohen's Kappa),
proposal metrics, baseline strategies, evidence ablations, and reproducible experiments.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c4_policy_aware_safety.contracts.enums import (
    PolicyFamily,
    ViolationStage,
)


class DatasetSplit(str, Enum):
    """Dataset partition assignment preventing data leakage across evaluations."""

    DEV = "DEV"
    PILOT = "PILOT"
    HELD_OUT = "HELD_OUT"


class LabelOrigin(str, Enum):
    """Provenance and authority of reference labels."""

    SYNTHETIC = "SYNTHETIC"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    ADJUDICATED = "ADJUDICATED"


class ReviewStatus(str, Enum):
    """Lifecycle status of reference label review."""

    PENDING_REVIEW = "PENDING_REVIEW"
    IN_AGREEMENT = "IN_AGREEMENT"
    DISAGREEMENT = "DISAGREEMENT"
    ADJUDICATED = "ADJUDICATED"
    FINALIZED = "FINALIZED"


class StrategyType(str, Enum):
    """Evaluation and generation baseline strategies."""

    C4_POLICY_AWARE = "C4_POLICY_AWARE"
    MANUAL_SUITE = "MANUAL_SUITE"
    GENERIC_MODEL_GENERATOR = "GENERIC_MODEL_GENERATOR"
    TEXT_ONLY_EVALUATOR = "TEXT_ONLY_EVALUATOR"


class AblationType(str, Enum):
    """Evidence and grounding ablation configurations."""

    NONE = "NONE"
    NO_GROUNDING = "NO_GROUNDING"
    NO_PROVENANCE = "NO_PROVENANCE"
    NO_EFFECTS = "NO_EFFECTS"


class ExperimentStatus(str, Enum):
    """Lifecycle state of an evaluation experiment."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ReferenceAttribution(BaseModel):
    """Fine-grained reference attribution targets for an evaluation case."""

    rule_id: str | None = None
    source_id: str | None = None
    stage: str | None = None
    effect_target: str | None = None


class EvaluationCaseRecord(BaseModel):
    """Single reference test case within an evaluation dataset."""

    case_id: str
    project_id: str
    domain_id: str
    policy_family: PolicyFamily
    case_category: str
    scenario_group_id: str
    source_type: str
    contract_id: str
    contract_version: int
    fixture_version: str = "1.0"
    expected_applicability: bool
    expected_verdict: str  # PASS or FAIL
    reference_violation_stage: ViolationStage | None = None
    reference_attribution: ReferenceAttribution = Field(default_factory=ReferenceAttribution)
    reference_attacker_goal: str | None = None  # ACHIEVED, NOT_ACHIEVED, NOT_APPLICABLE
    reference_benign_utility: str | None = None  # SUCCESS, DEGRADED, FAILED, NOT_APPLICABLE
    label_origin: LabelOrigin = LabelOrigin.SYNTHETIC
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    split: DatasetSplit = DatasetSplit.DEV


class EvaluationDatasetRecord(BaseModel):
    """Versioned and frozen evaluation dataset partition."""

    dataset_id: str
    version: int = 1
    dataset_hash: str
    project_id: str
    domain_id: str
    cases: list[EvaluationCaseRecord] = Field(default_factory=list)
    split_counts: dict[str, int] = Field(default_factory=dict)
    is_frozen: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    frozen_at: datetime | None = None


# Independent Review Workflow
class ReviewPacket(BaseModel):
    """Packet presented to an independent reviewer with generated predictions hidden."""

    packet_id: str
    project_id: str
    case_id: str
    policy_excerpt: str
    tool_call_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewerDecision(BaseModel):
    """Individual judgment recorded by an independent reviewer."""

    review_id: str
    packet_id: str
    case_id: str
    reviewer_id: str  # e.g., "REVIEWER_1", "REVIEWER_2"
    verdict_decision: str  # PASS or FAIL
    rule_attribution: str | None = None
    rationale: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AdjudicationRecord(BaseModel):
    """Resolution of disagreements between independent reviewers."""

    adjudication_id: str
    case_id: str
    adjudicator_id: str
    final_verdict: str
    final_attribution: ReferenceAttribution
    resolution_notes: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InterRaterAgreement(BaseModel):
    """Cohen's Kappa and inter-rater agreement statistics between two reviewers."""

    total_cases: int
    agreed_count: int
    disagreed_count: int
    observed_agreement_po: float
    chance_agreement_pe: float
    cohens_kappa: float | None = None
    interpretation: str


# Proposal Metrics
class MetricValue(BaseModel):
    """Individual metric calculation with explicit population and denominator status."""

    value: float | None = None
    numerator: int = 0
    denominator: int = 0
    status: str = "COMPUTED"  # COMPUTED, ZERO_DENOMINATOR, NO_DATA
    reason: str | None = None


class ComprehensiveEvaluationReport(BaseModel):
    """Full research-evaluation metrics report across all proposal categories."""

    report_id: str
    project_id: str
    domain_id: str
    dataset_id: str
    dataset_version: int
    split: DatasetSplit
    strategy_type: StrategyType
    ablation_type: AblationType

    # 1. Policy Extraction
    extraction_precision: MetricValue
    extraction_recall: MetricValue
    extraction_f1: MetricValue
    provenance_accuracy: MetricValue

    # 2. Generated Tests
    case_validity_rate: MetricValue
    planned_coverage: MetricValue
    observed_coverage: MetricValue
    accepted_unexercised_count: int = 0

    # 3. Violation Detection
    detection_precision: MetricValue
    detection_recall: MetricValue
    detection_f1: MetricValue
    false_pass_rate: MetricValue
    inconclusive_count: int = 0
    not_exercised_count: int = 0
    abstention_count: int = 0

    # 4. Attacks and Exposure
    exposure_rate: MetricValue
    attack_success_rate: MetricValue
    attempt_goal_rate: MetricValue
    commit_goal_rate: MetricValue
    unknown_exposure_count: int = 0

    # 5. Utility and Attribution
    benign_utility_rate: MetricValue
    false_refusal_rate: MetricValue
    rule_attribution_accuracy: MetricValue
    source_attribution_accuracy: MetricValue
    stage_attribution_accuracy: MetricValue
    effect_attribution_accuracy: MetricValue

    # 6. Regression and Effort
    affected_identification_precision: MetricValue
    affected_identification_recall: MetricValue
    adaptation_success_rate: MetricValue
    fresh_executions: int = 0
    historical_re_evaluations: int = 0
    reused_results: int = 0
    average_latency_ms: float = 0.0

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Experiment Orchestration
class ExperimentConfigRecord(BaseModel):
    """Configuration for reproducible evaluation experiment."""

    experiment_id: str
    project_id: str
    domain_id: str
    dataset_id: str
    dataset_version: int
    split: DatasetSplit
    strategy_type: StrategyType
    ablation_type: AblationType = AblationType.NONE
    repeat_count: int = 1
    seed: int = 42
    budget_limit: int = 100
    model_identifier: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentRunRecord(BaseModel):
    """Execution trial within an experiment."""

    run_id: str
    experiment_id: str
    trial_index: int
    status: ExperimentStatus = ExperimentStatus.COMPLETED
    executed_case_ids: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentReportRecord(BaseModel):
    """Consolidated experiment report with repeats and uncertainty summaries."""

    experiment_id: str
    project_id: str
    config: ExperimentConfigRecord
    status: ExperimentStatus = ExperimentStatus.COMPLETED
    runs: list[ExperimentRunRecord] = Field(default_factory=list)
    aggregated_metrics: dict[str, Any] = Field(default_factory=dict)
    per_domain_metrics: dict[str, Any] = Field(default_factory=dict)
    per_category_metrics: dict[str, Any] = Field(default_factory=dict)
    uncertainty_summary: dict[str, Any] = Field(default_factory=dict)
    # Where the predictions come from; SIMULATED results must not be reported as empirical findings.
    evidence_basis: str = "SIMULATED_FROM_REFERENCE_LABELS"
    limitations: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None
