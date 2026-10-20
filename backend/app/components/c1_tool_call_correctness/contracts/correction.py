from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CorrectionStatus(str, Enum):
    """Lifecycle status of a candidate correction attempt."""

    PENDING = "PENDING"
    GENERATED = "GENERATED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INELIGIBLE = "INELIGIBLE"
    FAILED = "FAILED"


class VerificationStepType(str, Enum):
    """Ordered steps in the independent verification plan."""

    REPRODUCE_ORIGINAL_FAILURE = "REPRODUCE_ORIGINAL_FAILURE"
    APPLY_PATCH = "APPLY_PATCH"
    BUILD_STATIC_CHECK = "BUILD_STATIC_CHECK"
    RERUN_ORIGINAL_CASE = "RERUN_ORIGINAL_CASE"
    RUN_REGRESSION_CHECKS = "RUN_REGRESSION_CHECKS"
    RUN_INDEPENDENT_ACCEPTANCE = "RUN_INDEPENDENT_ACCEPTANCE"


class StepExecutionStatus(str, Enum):
    """Outcome status for an individual verification step."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class ReviewDecision(str, Enum):
    """Developer review decision on a verified candidate correction."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class CandidatePatch(BaseModel):
    """Structured candidate source patch generated for a defect."""

    patch_id: str = Field(..., description="Unique patch identifier")
    diff_content: str = Field(
        ..., description="Unified diff string representing candidate change"
    )
    patch_hash: str = Field(..., description="SHA-256 hash of unified diff content")
    modified_files: list[str] = Field(
        default_factory=list, description="Repository-relative files touched"
    )
    additions_count: int = Field(default=0, ge=0)
    deletions_count: int = Field(default=0, ge=0)
    rationale: str = Field(
        default="", description="Technical rationale for the candidate fix"
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationCheckResult(BaseModel):
    """Outcome for a single mandatory verification check."""

    step_type: VerificationStepType = Field(
        ..., description="Type of verification step"
    )
    status: StepExecutionStatus = Field(..., description="Outcome of the check")
    is_mandatory: bool = Field(
        default=True, description="Whether passing this step is mandatory for VERIFIED"
    )
    expected_outcome: str = Field(..., description="Expected behavior or assertion")
    observed_outcome: str = Field(
        ..., description="Actual recorded behavior or exit state"
    )
    duration_ms: float = Field(default=0.0, ge=0.0)
    exit_code: int | None = Field(default=None)
    evidence_refs: list[str] = Field(
        default_factory=list, description="Associated evidence or log references"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic payload or error details"
    )


class ReviewRecord(BaseModel):
    """Developer review decision bound to the exact candidate patch hash."""

    decision: ReviewDecision = Field(default=ReviewDecision.PENDING)
    reviewer: str | None = Field(
        default=None, description="Username or ID of reviewing developer"
    )
    reason: str | None = Field(
        default=None, description="Review justification or feedback"
    )
    target_patch_hash: str | None = Field(
        default=None,
        description="Bound patch hash to prevent review on stale candidate",
    )
    reviewed_at: datetime | None = Field(default=None)
    audit_ref: str | None = Field(default=None, description="Audit tracking reference")


class CorrectionRecord(BaseModel):
    """Complete versioned record of a correction attempt, verification results, and developer decision."""

    correction_id: str = Field(..., description="Unique correction attempt ID")
    project_id: str = Field(..., description="Associated project ID")
    run_id: str = Field(..., description="Original execution run ID")
    case_id: str = Field(..., description="Original failing case ID")
    case_execution_id: str = Field(..., description="Associated case execution ID")
    diagnosis_id: str = Field(..., description="Corroborating diagnosis record ID")
    attempt_number: int = Field(default=1, ge=1)
    source_hash: str | None = Field(
        default=None, description="SHA-256 of inspected source snapshot"
    )
    source_commit: str | None = Field(default=None, description="Git commit reference")
    permitted_paths: list[str] = Field(
        default_factory=list, description="Permitted file paths scope"
    )
    candidate_patch: CandidatePatch | None = Field(default=None)
    status: CorrectionStatus = Field(default=CorrectionStatus.PENDING)
    is_verified: bool = Field(
        default=False,
        description="Strictly True only if EVERY mandatory check completes and passes",
    )
    ineligibility_reasons: list[str] = Field(default_factory=list)
    verification_results: list[VerificationCheckResult] = Field(default_factory=list)
    review: ReviewRecord = Field(default_factory=ReviewRecord)
    isolation_type: str = Field(
        default="DISPOSABLE_SUBPROCESS",
        description="Isolation boundary used: CONTAINER or DISPOSABLE_SUBPROCESS",
    )
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)


class CorrectionAttemptRequest(BaseModel):
    """Payload to request candidate correction and sandbox verification."""

    diagnosis_id: str = Field(
        ..., description="Diagnosis ID supporting an application code defect"
    )
    allowed_paths: list[str] | None = Field(
        default=None,
        description="Explicitly permitted relative file paths. If None, uses tool code mappings.",
    )
    source_root_path: str | None = Field(
        default=None,
        description="Repository root path containing source code for inspection and disposable copying",
    )
    code_version: str | None = Field(
        default=None, description="Optional commit or version reference"
    )
    patch_override: str | None = Field(
        default=None,
        description="Optional externally supplied patch (imported patch support)",
    )
    force_container_isolation: bool = Field(
        default=False,
        description="Require container isolation; fails if container daemon is unavailable",
    )
    idempotency_key: str | None = Field(
        default=None, description="Client idempotency key"
    )


class ReviewRequest(BaseModel):
    """Payload to accept or reject a verified candidate correction."""

    decision: ReviewDecision = Field(..., description="Decision: ACCEPTED or REJECTED")
    reviewer: str = Field(
        ..., min_length=1, description="Developer ID submitting review"
    )
    target_patch_hash: str = Field(
        ..., min_length=1, description="Exact patch hash confirming review target"
    )
    reason: str = Field(default="", description="Rationale or review notes")


class CorrectionDiffResponse(BaseModel):
    """Payload for developer diff inspection."""

    correction_id: str
    patch_id: str | None = None
    patch_hash: str | None = None
    source_hash: str | None = None
    diff_content: str = ""
    modified_files: list[str] = Field(default_factory=list)
    is_verified: bool = False
    review_decision: ReviewDecision = ReviewDecision.PENDING


class CorrectionSummary(BaseModel):
    """Summary record for listing correction history."""

    correction_id: str
    project_id: str
    run_id: str
    case_id: str
    diagnosis_id: str
    attempt_number: int
    status: CorrectionStatus
    is_verified: bool
    review_decision: ReviewDecision
    created_at: datetime
