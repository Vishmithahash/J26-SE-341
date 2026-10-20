from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CauseCategory(str, Enum):
    """Classification of the supported root cause for an observed tool-call failure.
    Kept strictly separate from the original test correctness verdict.
    """

    SUPPORTED_APPLICATION_CODE_DEFECT = "SUPPORTED_APPLICATION_CODE_DEFECT"
    AGENT_BEHAVIOUR = "AGENT_BEHAVIOUR"
    SPECIFICATION_OR_EXPECTATION_PROBLEM = "SPECIFICATION_OR_EXPECTATION_PROBLEM"
    UNKNOWN = "UNKNOWN"


class SourceRelationshipStatus(str, Enum):
    """Provenance status for contextual source data relationships.
    Equality alone does not establish provenance.
    """

    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvidenceAvailability(str, Enum):
    """Availability and completeness of corroborating execution evidence."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    INSUFFICIENT = "INSUFFICIENT"


class ExplanationMethod(str, Enum):
    """Method used to derive the explanation."""

    DETERMINISTIC_RULE_DERIVATION = "DETERMINISTIC_RULE_DERIVATION"
    MODEL_ASSISTED_PRESENTATION = "MODEL_ASSISTED_PRESENTATION"


class DiagnosisStatus(str, Enum):
    """Status of the diagnosis generation lifecycle."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


class CandidateCodeLocation(BaseModel):
    """Identified candidate repository code location linked to tool mapping and evidence."""

    file_path: str = Field(..., description="Repository relative source file path")
    function_name: str = Field(
        ..., description="Function or method name identified in source code"
    )
    line_start: int = Field(
        ..., ge=1, description="1-indexed line start in source file"
    )
    line_end: int = Field(..., ge=1, description="1-indexed line end in source file")
    ranking_score: int = Field(
        default=1,
        ge=1,
        description="Rank priority where 1 represents the highest supported relevance",
    )
    ranking_criteria: str = Field(
        ..., description="Documented rule justifying the candidate ranking"
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="IDs of evidence records or mismatch codes corroborating this candidate",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Explicit limitations or uncertainties in the source attribution",
    )


class CheckExplanationDetail(BaseModel):
    """Structured, evidence-linked explanation for an individual check outcome."""

    check_id: str = Field(..., description="Unique check identifier")
    matched_call_id: str | None = Field(
        default=None, description="Event ID of the matched tool call if observed"
    )
    tool_name: str | None = Field(
        default=None, description="Target tool evaluated by this check"
    )
    expected_behavior: str = Field(
        ..., description="Expected tool-selection or argument constraint requirement"
    )
    observed_behavior: str = Field(
        ..., description="Exact observed behavior recorded in execution evidence"
    )
    relevant_arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments under inspection"
    )
    recorded_tool_outputs: Any = Field(
        default=None, description="Output payload or error recorded from tool"
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Pointers to corroborating trace or log evidence",
    )
    evidence_availability: EvidenceAvailability = Field(
        default=EvidenceAvailability.COMPLETE,
        description="Availability status of supporting evidence",
    )
    source_relationship_status: SourceRelationshipStatus = Field(
        default=SourceRelationshipStatus.UNKNOWN,
        description="Status of contextual source link: OBSERVED, INFERRED, or UNKNOWN",
    )
    what_was_observed: str = Field(
        ..., description="Clear factual statement of what was recorded in evidence"
    )
    violated_requirement: str = Field(
        ..., description="Requirement identifier and specification text violated"
    )
    evidence_supported_findings: list[str] = Field(
        default_factory=list,
        description="Findings supported directly by recorded evidence",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Questions or factors that remain uncertain or unverified",
    )


class CaseDiagnosisRecord(BaseModel):
    """Complete versioned explanation and cause diagnosis for a case execution."""

    diagnosis_id: str = Field(..., description="Unique diagnosis identifier")
    project_id: str = Field(..., description="Associated project ID")
    run_id: str = Field(..., description="Associated execution run ID")
    case_execution_id: str = Field(..., description="Associated case execution ID")
    case_id: str = Field(..., description="Evaluated test case ID")
    attempt_number: int = Field(
        default=1, ge=1, description="Attempt number of the case execution"
    )
    requirement_version: str = Field(
        ..., description="Requirement version evaluated against"
    )
    evaluator_version: str = Field(
        ..., description="Version of the evaluator engine used for execution"
    )
    explanation_version: str = Field(
        default="c1-explanation-v1.0",
        description="Version of the explanation/diagnosis engine",
    )
    status: DiagnosisStatus = Field(
        default=DiagnosisStatus.COMPLETED,
        description="Diagnosis lifecycle completion status",
    )
    cause_category: CauseCategory = Field(
        ..., description="Supported failure cause classification"
    )
    explanation_summary: str = Field(
        ...,
        description="Concise human-readable explanation of why the failure occurred",
    )
    check_explanations: list[CheckExplanationDetail] = Field(
        default_factory=list,
        description="Detailed evidence-linked explanations for failing or inconclusive checks",
    )
    candidate_code_locations: list[CandidateCodeLocation] = Field(
        default_factory=list,
        description="Ranked candidate code locations when supported by evidence and source",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="IDs of evidence records corroborating this diagnosis",
    )
    source_hash: str | None = Field(
        default=None,
        description="SHA256 hash of the inspected source snapshot if code access was available",
    )
    explanation_method: ExplanationMethod = Field(
        default=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
        description="Explanation derivation method",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Performance metrics (retrieval_ms, analysis_ms, total_duration_ms)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiagnosisRequest(BaseModel):
    """Payload to request failure explanation and supported cause diagnosis."""

    case_id: str | None = Field(
        default=None,
        description="Optional case ID to diagnose a specific case. If None, diagnoses all failing cases in the run.",
    )
    source_root_path: str | None = Field(
        default=None,
        description="Optional repository root path for read-only AST source inspection",
    )
    code_version: str | None = Field(
        default=None, description="Optional repository code commit hash or version tag"
    )
    use_model_assisted: bool = Field(
        default=False,
        description="Whether to use model-assisted presentation if provider is available",
    )
    idempotency_key: str | None = Field(
        default=None, description="Client idempotency key to prevent duplicate runs"
    )


class DiagnosisSummary(BaseModel):
    """Summary record of a completed diagnosis."""

    diagnosis_id: str
    project_id: str
    run_id: str
    case_execution_id: str
    case_id: str
    attempt_number: int
    cause_category: CauseCategory
    explanation_summary: str
    candidate_count: int = 0
    status: DiagnosisStatus
    created_at: datetime
