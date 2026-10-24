"""Linked runtime records, safe serialization, and local export.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 2 - One-tool integration, matched trials, verified timeout exposure and safeguards.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    RecoveryActor,
    TargetMode,
)


class TrialRole(str, Enum):
    """Role of a trial within a matched pair."""

    CLEAN = "CLEAN"
    FAULT = "FAULT"


class ReadinessStatus(str, Enum):
    """Pre-execution readiness verdict."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class ExecutionStatus(str, Enum):
    """Runtime execution health and completion status."""

    COMPLETED = "COMPLETED"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class ExposureStatus(str, Enum):
    """Independent exposure status establishing whether injection occurred."""

    CONFIRMED = "CONFIRMED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    EXPOSURE_UNKNOWN = "EXPOSURE_UNKNOWN"


class CleanQualification(str, Enum):
    """Qualification status of the clean baseline control."""

    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    UNKNOWN = "UNKNOWN"


class FixtureComparability(str, Enum):
    """Verification that clean and fault trials began at equivalent logical starting states."""

    EQUIVALENT_LOGICAL_STATE = "EQUIVALENT_LOGICAL_STATE"
    NON_EQUIVALENT = "NON_EQUIVALENT"
    UNKNOWN = "UNKNOWN"


class ForwardingDecision(str, Enum):
    """Interceptor decision on whether request was forwarded to target."""

    FORWARDED = "FORWARDED"
    PREVENTED_INJECTED_TIMEOUT = "PREVENTED_INJECTED_TIMEOUT"
    PREVENTED_INJECTED_FAULT = "PREVENTED_INJECTED_FAULT"
    FORWARDED_COMMITTED_RESPONSE_WITHHELD = "FORWARDED_COMMITTED_RESPONSE_WITHHELD"


class TimeoutBoundaryType(str, Enum):
    """Distinction of timeout boundary recorded."""

    CALLER_TIMEOUT_EXCEEDED = "CALLER_TIMEOUT_EXCEEDED"
    ELAPSED_TOOL_CALL_DEADLINE = "ELAPSED_TOOL_CALL_DEADLINE"
    ACTUAL_TRANSPORT_TIMEOUT = "ACTUAL_TRANSPORT_TIMEOUT"
    IMMEDIATE_SYNTHETIC_EXCEPTION = "IMMEDIATE_SYNTHETIC_EXCEPTION"


# ---------------------------------------------------------------------------
# Sanitization & Fingerprinting
# ---------------------------------------------------------------------------

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "private_key",
    "conn_str",
    "dsn",
)


def sanitize_arguments(data: Any) -> Any:
    """Recursively sanitize arguments by completely stripping or redacting sensitive keys.

    Credentials and tokens are never stored, hashed, or serialized.
    """
    if isinstance(data, Mapping):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).lower()
            if any(sub in k_str for sub in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = sanitize_arguments(v)
        return sanitized
    if isinstance(data, list):
        return [sanitize_arguments(item) for item in data]
    return data


def compute_argument_fingerprint(arguments: dict[str, Any]) -> str:
    """Compute a deterministic hash fingerprint of sanitized arguments.

    Excludes raw secret values.
    """
    cleaned = sanitize_arguments(arguments)
    canonical = json.dumps(cleaned, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Linked Evidence Models
# ---------------------------------------------------------------------------


class RuntimeEvent(BaseModel):
    """Single discrete linked event recorded during execution."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        default_factory=lambda: f"evt-{uuid4().hex[:12]}", min_length=1, max_length=64
    )
    timestamp_iso: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = Field(min_length=1, max_length=64)
    tool_id: str = Field(min_length=1, max_length=128)
    occurrence: int = Field(ge=0)
    forwarding_decision: ForwardingDecision | None = None
    safe_argument_fingerprint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class FaultEpisodeRecord(BaseModel):
    """Linked record of the single targeted fault episode."""

    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(
        default_factory=lambda: f"ep-{uuid4().hex[:12]}", min_length=1, max_length=64
    )
    target_tool_id: str
    target_occurrence: int
    interception_hook: InterceptionHook
    effect_phase: EffectPhase
    fault_family: FaultFamily
    fault_mode: str
    declared_caller_timeout_ms: int
    fault_timing_ms: int | None = None
    timeout_boundary_type: TimeoutBoundaryType
    prevented_forwarding: bool
    caller_observed_timeout: bool
    elapsed_wait_ms: float
    consumed_atomically: bool = True

    # Phase 3 additions:
    fault_status_code: int | None = None
    retry_after_seconds: int | None = None
    unavailability_mode: str | None = None
    malformed_fragment: str | None = None
    committed_operation_id: str | None = None
    independent_observation_confirmed: bool = False
    cancellation_reason: str | None = None


class StateObservationReference(BaseModel):
    """Authoritative versioned observation reference projected from captured state snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    snapshot_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    entity_id: str | None = Field(default=None, max_length=128)
    captured_at_iso: str | None = None
    observation_scope: str = Field(default="post_recovery", max_length=64)
    fingerprint: str | None = None


class TrialEvidence(BaseModel):
    """Complete evidence record for one trial (CLEAN or FAULT)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    case_id: str
    pair_id: str
    trial_id: str
    run_id: str
    trial_role: TrialRole
    target_mode: TargetMode
    caller_identity: CallerIdentity
    recovery_actor: RecoveryActor

    fixture_namespace: str
    initial_state_fingerprint: str
    final_state_fingerprint: str

    events: list[RuntimeEvent] = Field(default_factory=list)
    episodes: list[FaultEpisodeRecord] = Field(default_factory=list)

    tool_calls_count: int = 0
    subsequent_calls_count: int = 0
    observed_effects: list[str] = Field(default_factory=list)
    execution_status: ExecutionStatus
    caller_outcome: str
    cleanup_status: CleanupStatus
    evidence_complete: bool = True

    snapshot_id: str | None = Field(
        default=None,
        description="Retained post-recovery observation snapshot identifier.",
    )
    observed_entity_id: str | None = Field(
        default=None,
        description="Retained observed entity identifier.",
    )
    observation_reference: StateObservationReference | None = Field(
        default=None,
        description="Authoritative versioned observation reference projected from captured state snapshot.",
    )


class MatchedPairEvidence(BaseModel):
    """Comprehensive paired execution record linking baseline clean control and fault trial."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    project_id: str
    case_id: str
    pair_id: str
    run_id: str

    readiness_status: ReadinessStatus
    readiness_reasons: list[str] = Field(default_factory=list)

    target_mode: TargetMode
    caller_identity: CallerIdentity
    configuration_snapshot: dict[str, Any]

    clean_trial: TrialEvidence
    fault_trial: TrialEvidence

    fixture_comparability: FixtureComparability
    clean_qualification: CleanQualification
    exposure_assessed: bool = True
    exposure_status: ExposureStatus
    exposure_reasons: list[str] = Field(default_factory=list)

    cleanup_status: CleanupStatus
    recovery_verdict: None = None  # Recovery scoring is strictly deferred
    interpretation_limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Linkage Validation & Export
# ---------------------------------------------------------------------------


def validate_evidence_linkage(evidence: MatchedPairEvidence) -> bool:
    """Verify that all records within a matched pair share linked identifiers."""
    pair_id = evidence.pair_id
    case_id = evidence.case_id
    project_id = evidence.project_id
    run_id = evidence.run_id

    for role_name, trial in [
        ("clean", evidence.clean_trial),
        ("fault", evidence.fault_trial),
    ]:
        if trial.pair_id != pair_id:
            raise ValueError(
                f"Linkage violation: {role_name} trial pair_id '{trial.pair_id}' != '{pair_id}'."
            )
        if trial.case_id != case_id:
            raise ValueError(
                f"Linkage violation: {role_name} trial case_id '{trial.case_id}' != '{case_id}'."
            )
        if trial.project_id != project_id:
            raise ValueError(
                f"Linkage violation: {role_name} trial project_id '{trial.project_id}' != '{project_id}'."
            )
        if trial.run_id != run_id:
            raise ValueError(
                f"Linkage violation: {role_name} trial run_id '{trial.run_id}' != '{run_id}'."
            )
        for ev in trial.events:
            if not ev.event_id:
                raise ValueError(
                    f"Linkage violation: event in {role_name} trial missing event_id."
                )

    for ep in evidence.fault_trial.episodes:
        if not ep.episode_id:
            raise ValueError("Linkage violation: fault episode missing episode_id.")

    return True


def export_evidence_to_file(
    evidence: MatchedPairEvidence,
    export_dir: Path | str = "evidence_output",
    filename: str | None = None,
) -> Path:
    """Safely export sanitized versioned JSON evidence to a local file.

    Validates linkage first and guarantees no accidental overwrite via exclusive creation.
    """
    validate_evidence_linkage(evidence)

    target_dir = Path(export_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp_slug = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = f"evidence_{evidence.pair_id}_{timestamp_slug}.json"

    file_path = target_dir / filename
    if file_path.exists():
        # Prevent accidental overwrite with unique suffix
        filename = f"evidence_{evidence.pair_id}_{uuid4().hex[:8]}_{int(datetime.now().timestamp())}.json"
        file_path = target_dir / filename

    content = evidence.model_dump_json(indent=2)
    with open(file_path, "x", encoding="utf-8") as f:
        f.write(content)

    return file_path
