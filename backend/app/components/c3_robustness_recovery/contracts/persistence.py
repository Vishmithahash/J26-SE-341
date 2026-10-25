"""Pydantic v2 typed persistence, query, import, and reporting contracts for Component 3 Phase 5.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

import hashlib
import json
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.schemas import CandidateFaultCase
from app.components.c3_robustness_recovery.runtime.evidence import (
    MatchedPairEvidence,
    sanitize_arguments,
)

T = TypeVar("T")


def compute_content_digest(data: Any) -> str:
    """Compute a deterministic SHA-256 content digest of an arbitrary object or dict."""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    sanitized = sanitize_arguments(data)
    canonical = json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ExecutionTrackingStatus(str, Enum):
    """Lifecycle status of a tracked C3 suite execution."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Suite Storage Contracts
# ---------------------------------------------------------------------------


class SuiteImportRequest(BaseModel):
    """Request to import and persist a verified frozen suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1, description="Project scope identifier.")
    frozen_suite: FrozenSuite = Field(..., description="Frozen suite to persist.")


class SuiteRecordResponse(BaseModel):
    """Stored frozen suite record response."""

    model_config = ConfigDict(extra="forbid")

    suite_id: str
    suite_digest: str
    project_id: str
    task_id: str
    tool_id: str
    domain: str
    schema_version: str
    generator_version: str
    total_cases: int
    created_at_utc: str
    frozen_suite: FrozenSuite


class CaseRecordResponse(BaseModel):
    """Stored candidate fault case snapshot response."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    suite_digest: str
    case_fingerprint: str
    content_digest: str
    project_id: str
    case_family_id: str
    fault_family: str
    effect_phase: str
    interception_hook: str
    target_tool_id: str
    case_order: int
    candidate_case: CandidateFaultCase
    created_at_utc: str


# ---------------------------------------------------------------------------
# Execution Tracking Contracts
# ---------------------------------------------------------------------------


class ExecutionCreateRequest(BaseModel):
    """Create a tracked execution manifest before target activity begins."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(
        default_factory=lambda: f"exec-{uuid4().hex[:12]}",
        description="Unique suite execution identifier.",
    )
    suite_digest: str = Field(..., min_length=1, description="Digest of frozen suite.")
    project_id: str = Field(..., min_length=1, description="Project scope identifier.")
    target_mode: str = Field("DEMONSTRATION", description="DEMONSTRATION or AUT.")
    caller_identity: str = Field(
        "SCRIPTED_CALLER", description="SCRIPTED_CALLER or AGENT."
    )
    planned_cases: list[str] = Field(
        default_factory=list,
        description="Ordered list of case IDs planned for execution.",
    )
    configuration_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Environment and runner configuration snapshot.",
    )


class ExecutionRecordResponse(BaseModel):
    """Tracked suite execution status response."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    suite_digest: str
    suite_id: str
    project_id: str
    target_mode: str
    caller_identity: str
    status: ExecutionTrackingStatus
    planned_cases_count: int
    executed_cases_count: int
    blocked_cases_count: int
    unsupported_cases_count: int
    cancelled_cases_count: int
    error_cases_count: int
    halt_reason: str | None = None
    started_at_utc: str
    completed_at_utc: str | None = None
    manifest_snapshot: dict[str, Any] = Field(default_factory=dict)


class ExecutionArtifactImportRequest(BaseModel):
    """Import a completed or partial execution artifact without executing it."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    suite_digest: str = Field(..., min_length=1)
    execution_id: str = Field(
        default_factory=lambda: f"exec-{uuid4().hex[:12]}", min_length=1
    )
    target_mode: str = Field("DEMONSTRATION")
    caller_identity: str = Field("SCRIPTED_CALLER")
    status: ExecutionTrackingStatus = Field(ExecutionTrackingStatus.COMPLETED)
    planned_cases_count: int = Field(0, ge=0)
    executed_cases_count: int = Field(0, ge=0)
    blocked_cases_count: int = Field(0, ge=0)
    unsupported_cases_count: int = Field(0, ge=0)
    cancelled_cases_count: int = Field(0, ge=0)
    error_cases_count: int = Field(0, ge=0)
    halt_reason: str | None = None
    manifest_snapshot: dict[str, Any] = Field(default_factory=dict)
    case_evidences: list[MatchedPairEvidence] = Field(
        default_factory=list,
        description="Optional list of matched pair evidence records to import transactionally.",
    )


# ---------------------------------------------------------------------------
# Matched Pair Evidence Storage Contracts
# ---------------------------------------------------------------------------


class MatchedPairImportRequest(BaseModel):
    """Import a linked matched trial pair evidence record."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    execution_id: str | None = Field(None, description="Optional tracked execution ID.")
    evidence: MatchedPairEvidence = Field(..., description="Matched pair evidence.")


class MatchedPairRecordResponse(BaseModel):
    """Stored matched trial pair record response."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str
    execution_id: str | None
    case_id: str
    project_id: str
    run_id: str
    clean_trial_id: str
    fault_trial_id: str
    readiness_status: str
    clean_qualification: str
    exposure_status: str
    exposure_assessed: bool
    cleanup_status: str
    clean_execution_status: str
    fault_execution_status: str
    evidence_complete: bool
    evidence_digest: str
    created_at_utc: str
    evidence: MatchedPairEvidence


# ---------------------------------------------------------------------------
# Evaluation Storage & Computation Contracts
# ---------------------------------------------------------------------------


class EvaluationComputeRequest(BaseModel):
    """Request to compute and persist a recovery evaluation from stored evidence."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    pair_id: str = Field(..., min_length=1)
    c2_facts: list[C2AssertionFact] = Field(
        default_factory=list, description="Discrete assertion facts."
    )
    evaluator_version: str = Field("1.1.0", min_length=1)
    rule_set_version: str = Field("1.1.0", min_length=1)
    pinned_mappings: list[Any] | None = Field(
        default=None, description="Optional explicit pinned C2-to-C3 assertion mappings."
    )


class ControlledExecutionRequest(BaseModel):
    """Request to launch a controlled trial run for an eligible stored suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1, description="Project scope identifier.")
    suite_id_or_digest: str = Field(
        ..., min_length=1, description="Stored suite ID or cryptographic digest."
    )
    execution_mode: str = Field(
        "DEMONSTRATION",
        description=(
            "Target execution mode for the controlled runner: DEMONSTRATION only. Live NexaCart "
            "runs use POST /api/v1/c3/live/nexacart/executions."
        ),
    )
    max_suite_duration_sec: float = Field(
        60.0, ge=1.0, le=300.0, description="Overall suite execution time limit in seconds."
    )
    per_case_timeout_sec: float = Field(
        10.0, ge=1.0, le=60.0, description="Per-case execution time limit in seconds."
    )


class ControlledExecutionResponse(BaseModel):
    """Execution response summary for native controlled trial execution."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    suite_id: str
    suite_digest: str
    project_id: str
    target_mode: str
    status: str
    total_cases: int
    executed_cases: int
    blocked_cases: int
    unsupported_cases: int
    confirmed_exposure_count: int
    not_triggered_exposure_count: int
    unknown_exposure_count: int
    pair_ids: list[str] = Field(default_factory=list)
    halt_reason: str | None = None
    case_results: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationRecordResponse(BaseModel):
    """Stored recovery evaluation result response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    pair_id: str
    case_id: str
    project_id: str
    evaluator_version: str
    rule_set_version: str
    evaluation_status: str
    recovery_verdict: RecoveryVerdict | None
    first_violated_rule: str | None
    actor_attribution: str
    inputs_digest: str
    created_at_utc: str
    evaluation: RecoveryEvaluationResult


# ---------------------------------------------------------------------------
# Pagination & Query Filter Contracts
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Standard bounded pagination parameters."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(50, ge=1, le=200, description="Page limit (max 200).")
    offset: int = Field(0, ge=0, description="Page offset.")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated envelope."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Reporting Contracts
# ---------------------------------------------------------------------------


class RecoveryVerdictCounts(BaseModel):
    """Breakdown of authoritative recovery verdicts."""

    model_config = ConfigDict(extra="forbid")

    pass_completed_count: int = 0
    pass_graceful_count: int = 0
    fail_count: int = 0
    inconclusive_count: int = 0
    not_evaluated_count: int = 0


class ExecutionReportResponse(BaseModel):
    """Comprehensive structured execution and recovery evaluation report."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    execution_id: str
    suite_id: str
    suite_digest: str
    project_id: str
    target_mode: str
    caller_identity: str
    status: str
    evaluator_version: str
    rule_set_version: str
    generated_at_utc: str

    # Explicit Denominators and Counts
    denominators: dict[str, str] = Field(
        default_factory=lambda: {
            "planned_cases": "Total candidate fault cases defined in the frozen suite manifest.",
            "executed_pairs": "Total matched trial pairs initiated by the runner.",
            "evaluated_trials": "Total fault trials evaluated by the recovery evaluation engine.",
        }
    )

    planned_cases_count: int
    executed_cases_count: int
    blocked_cases_count: int
    unsupported_cases_count: int
    cancelled_cases_count: int
    error_cases_count: int

    # Clean Baseline Qualification (per pair)
    clean_qualified_count: int = 0
    clean_disqualified_count: int = 0
    clean_indeterminate_count: int = 0

    # Exposure Outcomes (per pair)
    confirmed_exposure_count: int = 0
    not_triggered_exposure_count: int = 0
    unknown_exposure_count: int = 0

    # Recovery Verdicts (per eligible evaluated pair)
    verdict_counts: RecoveryVerdictCounts = Field(default_factory=RecoveryVerdictCounts)

    # Cleanup Certainty
    cleanup_verified_count: int = 0
    cleanup_uncertain_count: int = 0

    # Evaluator Rule Violations Summary
    rule_violation_counts: dict[str, int] = Field(default_factory=dict)

    # Limitations & Attribution
    demonstration_mode: bool = True
    demonstration_notes: list[str] = Field(default_factory=list)
    clean_control_notes: list[str] = Field(default_factory=list)
    fact_provenances: list[str] = Field(default_factory=list)

    # Detailed Case Summaries
    case_reports: list[dict[str, Any]] = Field(default_factory=list)
