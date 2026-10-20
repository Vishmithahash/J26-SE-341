from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.diagnosis import CauseCategory
from app.components.c1_tool_call_correctness.contracts.results import CorrectnessVerdict


class DatasetSplit(str, Enum):
    TRAIN_DEV = "train_dev"
    VALIDATION = "validation"
    HELD_OUT_TEST = "held_out_test"


class BaselineType(str, Enum):
    SCHEMA_AND_CALL_ONLY = "SCHEMA_AND_CALL_ONLY"
    MODEL_ARGUMENT_JUDGE = "MODEL_ARGUMENT_JUDGE"
    UNLINKED_DIAGNOSIS = "UNLINKED_DIAGNOSIS"
    REDUCED_EVIDENCE_NO_REQUIREMENTS = "REDUCED_EVIDENCE_NO_REQUIREMENTS"
    REDUCED_EVIDENCE_NO_SOURCE = "REDUCED_EVIDENCE_NO_SOURCE"
    REDUCED_EVIDENCE_NO_CODE = "REDUCED_EVIDENCE_NO_CODE"


class ReferenceCodeLocation(BaseModel):
    file_path: str
    function_name: str | None = None
    line_number: int | None = None


class ReferenceLabelCreate(BaseModel):
    """Independently reviewed ground truth label specification."""

    case_id: str
    suite_id: str | None = None
    task_family: str = Field(
        ...,
        description="Underlying task or defect family. Used for group-aware dataset splits and bootstrap clustering.",
    )
    dataset_split: DatasetSplit = DatasetSplit.TRAIN_DEV
    ground_truth_verdict: CorrectnessVerdict
    ground_truth_cause: CauseCategory | None = None
    ground_truth_code_locations: list[ReferenceCodeLocation] = Field(
        default_factory=list
    )
    valid_evidence_refs: list[str] = Field(default_factory=list)
    reviewer_id: str
    label_version: str = "v1.0"
    disagreements: list[str] = Field(default_factory=list)
    adjudication: dict[str, Any] = Field(default_factory=dict)
    is_held_out: bool = False


class ReferenceLabelRecord(ReferenceLabelCreate):
    id: str
    project_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReferenceLabelImportRequest(BaseModel):
    labels: list[ReferenceLabelCreate] = Field(..., min_length=1)


class ReferenceLabelImportResponse(BaseModel):
    imported_count: int
    updated_count: int
    dataset_splits_distribution: dict[str, int]
    task_families_count: int


class MetricWithDetail(BaseModel):
    """A documented research metric with explicit numerator, denominator, and value."""

    value: float = Field(
        ..., description="Calculated metric value in range [0.0, 1.0] or rate."
    )
    numerator: int = Field(
        ..., description="Count of qualifying positive cases / successes."
    )
    denominator: int = Field(
        ..., description="Count of total eligible cases in evaluation scope."
    )
    formula: str = Field(..., description="Mathematical definition.")
    notes: str = ""
    ci_95_lower: float | None = Field(
        default=None, description="Bootstrap 95% CI lower bound."
    )
    ci_95_upper: float | None = Field(
        default=None, description="Bootstrap 95% CI upper bound."
    )


class AccuracyMetricsReport(BaseModel):
    """Documented Component 1 research metrics computed against independent ground truth labels."""

    project_id: str
    run_id: str | None = None
    dataset_split: DatasetSplit | None = None
    total_labelled_cases: int = 0
    total_evaluated_cases: int = 0

    # 1. Test case generation validity & coverage
    generated_case_validity: MetricWithDetail
    requirement_coverage: MetricWithDetail

    # 2. Correctness evaluation precision & recall
    failure_detection_precision: MetricWithDetail
    failure_detection_recall: MetricWithDetail
    inconclusive_rate: MetricWithDetail
    decision_coverage: MetricWithDetail

    # 3. Diagnosis accuracy & code localisation
    diagnosis_accuracy_all: MetricWithDetail
    diagnosis_accuracy_decided: MetricWithDetail
    top_1_code_localisation_accuracy: MetricWithDetail
    top_3_code_localisation_accuracy: MetricWithDetail
    false_code_blame_rate: MetricWithDetail

    # 4. Evidence link accuracy & coverage
    evidence_link_accuracy: MetricWithDetail
    evidence_coverage: MetricWithDetail

    # 5. Verification & candidate correction metrics
    verified_correction_rate: MetricWithDetail
    verification_success_rate: MetricWithDetail
    regression_check_failure_rate: MetricWithDetail

    # 6. Timing and latency metrics (ms)
    median_diagnosis_time_ms: float = 0.0
    p95_diagnosis_time_ms: float = 0.0
    median_verification_time_ms: float = 0.0
    p95_verification_time_ms: float = 0.0


class BaselineEvaluationRequest(BaseModel):
    baseline_type: BaselineType
    run_id: str
    case_id: str
    model_provider_name: str | None = None


class BaselineEvaluationResult(BaseModel):
    baseline_type: BaselineType
    case_id: str
    is_available: bool = True
    unavailability_reason: str | None = None
    verdict: CorrectnessVerdict | None = None
    cause_category: CauseCategory | None = None
    candidate_code_locations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0
