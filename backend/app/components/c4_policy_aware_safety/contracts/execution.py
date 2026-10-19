from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import (
    ExposureStatus,
)


class TargetExecutionMode(str, Enum):
    """Target execution mode for C4 testing."""

    SIMULATED = "SIMULATED"
    LIVE_AUT = "LIVE_AUT"


class SimulatedAgentBehavior(str, Enum):
    """Configurable scripted behaviors for the controlled offline simulated adapter."""

    COMPLIANT = "COMPLIANT"
    UNAUTHORIZED_ATTEMPT_BLOCKED = "UNAUTHORIZED_ATTEMPT_BLOCKED"
    PROHIBITED_EFFECT_COMMITTED = "PROHIBITED_EFFECT_COMMITTED"
    DISCLOSURE_EXFILTRATION = "DISCLOSURE_EXFILTRATION"
    IGNORES_INJECTION_SOURCE = "IGNORES_INJECTION_SOURCE"
    MISSING_INSTRUMENTATION = "MISSING_INSTRUMENTATION"
    INCOMPLETE_TRACE = "INCOMPLETE_TRACE"
    OBEYS_FAKE_APPROVAL = "OBEYS_FAKE_APPROVAL"
    UNRESOLVED_PROVENANCE = "UNRESOLVED_PROVENANCE"
    FIXTURE_PREPARATION_FAILURE = "FIXTURE_PREPARATION_FAILURE"
    FIXTURE_CLEANUP_FAILURE = "FIXTURE_CLEANUP_FAILURE"


class ExecutionStatus(str, Enum):
    """Lifecycle status of a C4 test case execution run."""

    PENDING = "PENDING"
    PREPARING_FIXTURE = "PREPARING_FIXTURE"
    READY = "READY"
    BLOCKED_BEFORE_INVOCATION = "BLOCKED_BEFORE_INVOCATION"
    INVOKING_AGENT = "INVOKING_AGENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


class AttackerObjectiveOutcome(str, Enum):
    """Structured evaluation of whether the attacker objective was achieved."""

    ACHIEVED = "ACHIEVED"
    BLOCKED = "BLOCKED"
    NOT_ACHIEVED = "NOT_ACHIEVED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TaskUtilityOutcome(str, Enum):
    """Assessment of whether the benign task succeeded independently of safety."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CleanupStatus(str, Enum):
    """Outcome of fixture post-trial reset and cleanup."""

    CLEANED_AND_VERIFIED = "CLEANED_AND_VERIFIED"
    CLEANUP_FAILED = "CLEANUP_FAILED"
    SKIPPED = "SKIPPED"


class C4RuntimeReadinessReport(BaseModel):
    """Report on adapter and fixture readiness before invoking an agent."""

    model_config = ConfigDict(extra="forbid")

    is_ready: bool
    blockers: list[str] = Field(default_factory=list)
    adapter_id: str
    adapter_version: str
    execution_mode: TargetExecutionMode
    supported_capabilities: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    fixture_isolated: bool = True


class C4ExecutionRequest(BaseModel):
    """Request payload to execute a frozen policy test case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int = 1
    contract_id: str
    contract_version: int = 1
    binding_id: str
    binding_version: int = 1
    adapter_id: str = "simulated_c4_adapter"
    execution_mode: TargetExecutionMode = TargetExecutionMode.SIMULATED
    simulated_behavior: SimulatedAgentBehavior = SimulatedAgentBehavior.COMPLIANT
    idempotency_key: str | None = None


class C4ExecutionRunRecord(BaseModel):
    """Persisted record of a completed or blocked C4 test execution."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    case_id: str
    case_version: int
    contract_id: str
    contract_version: int
    binding_id: str
    binding_version: int
    fixture_versions: dict[str, int] = Field(default_factory=dict)
    adapter_id: str
    adapter_version: str
    adapter_config_digest: str
    execution_mode: TargetExecutionMode
    simulated_behavior: str | None = None
    status: ExecutionStatus
    exposure_status: ExposureStatus
    policy_verdict: str
    attacker_objective_outcome: AttackerObjectiveOutcome
    task_utility_outcome: TaskUtilityOutcome
    cleanup_status: CleanupStatus
    idempotency_key: str | None = None
    pre_cleanup_effects: list[dict[str, Any]] = Field(default_factory=list)
    raw_evidence_ref: str | None = None
    evaluation_report_summary: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
