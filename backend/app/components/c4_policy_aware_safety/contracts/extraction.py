"""Contracts for C4 Phase 4 natural-language policy extraction and review."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractionJobStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ExtractionReadinessStatus(str, Enum):
    READY = "READY"
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    MISSING_ARTIFACT = "MISSING_ARTIFACT"
    INVALID_OPTIONS = "INVALID_OPTIONS"


class ExtractionReadinessReport(BaseModel):
    """Readiness report for natural-language extraction provider."""

    model_config = ConfigDict(extra="forbid")

    ready: bool = Field(..., description="Whether extraction can proceed")
    status: ExtractionReadinessStatus = Field(..., description="Readiness status code")
    provider_id: str = Field(..., description="Identifier of the extraction provider")
    model_identifier: str | None = Field(default=None, description="Configured model name")
    supported_policy_families: list[str] = Field(
        default_factory=lambda: ["AUTHORIZATION", "CONFIDENTIALITY", "INSTRUCTION_AUTHORITY"]
    )
    blockers: list[str] = Field(default_factory=list, description="Reason codes or explanations for blockers")


class ExtractionJobCreate(BaseModel):
    """Request to initiate a natural-language policy extraction job."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., description="Policy artifact ID to extract rules from")
    artifact_version: int = Field(..., ge=1, description="Immutable version of the artifact")
    provider_id: str = Field(
        default="shared_llm",
        description=(
            "Extraction provider: 'shared_llm' (the user's selected QA model; local Ollama by default) "
            "or 'offline_mock' (deterministic test fixture)"
        ),
    )
    options: dict[str, Any] = Field(
        default_factory=dict, description="Extraction settings (e.g. temperature, provider mode, max_tokens)"
    )
    domain_id: str | None = Field(
        default=None,
        description=(
            "Domain whose binding (roles, tools, resources) the candidates are validated against; "
            "default: the project's NexaCart binding when imported, else the e-commerce demo profile"
        ),
    )


class CandidateRuleReviewRequest(BaseModel):
    """Human or automated review decision for an extracted candidate rule."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., description="'ACCEPTED' or 'REJECTED'")
    reviewer: str = Field(..., min_length=1, description="Reviewer actor ID or username")
    review_notes: str | None = Field(default=None, description="Optional notes explaining decision")
    is_synthetic_review: bool = Field(
        default=True,
        description="True if review decision is from automated test/dev harness; False for real human review",
    )


class C4ExtractionJobRecord(BaseModel):
    """Persisted record of an extraction job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Unique job identifier")
    project_id: str = Field(..., description="Project owning the job")
    artifact_id: str = Field(..., description="Extracted artifact ID")
    artifact_version: int = Field(..., description="Extracted artifact version")
    provider_id: str = Field(..., description="Extraction provider used")
    model_identifier: str = Field(..., description="Model identifier")
    status: ExtractionJobStatus = Field(..., description="Job status")
    readiness_status: ExtractionReadinessStatus = Field(..., description="Readiness status at run time")
    prompt_template_version: str = Field(default="v4.0.0", description="Version of extraction prompt template")
    schema_version: str = Field(default="c4_candidate_v1", description="Supported candidate schema version")
    options: dict[str, Any] = Field(default_factory=dict, description="Generation options used")
    job_metadata: dict[str, Any] = Field(default_factory=dict, description="Latency, token usage, cost metrics")
    candidates_extracted: list[str] = Field(
        default_factory=list, description="List of extracted candidate rule IDs"
    )
    validation_issues: list[dict[str, Any]] = Field(
        default_factory=list, description="Validation issues identified across candidates"
    )
    error_message: str | None = Field(default=None, description="Error message if extraction failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
