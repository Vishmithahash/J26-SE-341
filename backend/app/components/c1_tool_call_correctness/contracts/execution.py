from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import (
    EvidenceRef,
    RunStatus,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CheckLevelResult,
    CorrectnessVerdict,
)


class TraceCompleteness(str, Enum):
    """Integrity and completeness of the trace captured from the execution session."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    CORRUPTED = "CORRUPTED"
    MISSING = "MISSING"


class EventStatus(str, Enum):
    """Runtime execution status of a single captured tool event."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


class ExecutionReasonCode(str, Enum):
    """Stable reason codes for check evaluations and execution failures."""

    MATCH = "MATCH"
    FORBIDDEN_TOOL_INVOKED = "FORBIDDEN_TOOL_INVOKED"
    FORBIDDEN_TOOL_NOT_INVOKED = "FORBIDDEN_TOOL_NOT_INVOKED"
    REQUIRED_TOOL_MISSING = "REQUIRED_TOOL_MISSING"
    INCOMPLETE_TRACE_MISSING_TOOL = "INCOMPLETE_TRACE_MISSING_TOOL"
    INCOMPLETE_TRACE_FORBIDDEN_TOOL = "INCOMPLETE_TRACE_FORBIDDEN_TOOL"
    TOOL_COUNT_OUT_OF_BOUNDS = "TOOL_COUNT_OUT_OF_BOUNDS"
    SELF_CORRECTED_AFTER_REJECTED_CALL = "SELF_CORRECTED_AFTER_REJECTED_CALL"
    TOOL_ORDER_VIOLATION = "TOOL_ORDER_VIOLATION"
    ARGUMENT_MISSING = "ARGUMENT_MISSING"
    ARGUMENT_EXPLICIT_NULL_VIOLATION = "ARGUMENT_EXPLICIT_NULL_VIOLATION"
    ARGUMENT_UNEXPECTED_PRESENCE = "ARGUMENT_UNEXPECTED_PRESENCE"
    ARGUMENT_VALUE_MISMATCH = "ARGUMENT_VALUE_MISMATCH"
    ARGUMENT_TYPE_MISMATCH = "ARGUMENT_TYPE_MISMATCH"
    SOURCE_MATCH = "SOURCE_MATCH"
    SOURCE_VALUE_MISMATCH = "SOURCE_VALUE_MISMATCH"
    SOURCE_RECORD_MISSING = "SOURCE_RECORD_MISSING"
    SOURCE_PATH_MISSING = "SOURCE_PATH_MISSING"
    INSUFFICIENT_EVIDENCE_SATISFIED = "INSUFFICIENT_EVIDENCE_SATISFIED"
    INSUFFICIENT_EVIDENCE_UNASSESSABLE = "INSUFFICIENT_EVIDENCE_UNASSESSABLE"
    CALL_EXECUTION_FAILED = "CALL_EXECUTION_FAILED"
    EXECUTION_TIMED_OUT = "EXECUTION_TIMED_OUT"
    ADAPTER_ERROR = "ADAPTER_ERROR"
    FIXTURE_SETUP_FAILED = "FIXTURE_SETUP_FAILED"


class CapturedToolEvent(BaseModel):
    """Normalized tool call event captured during agent execution."""

    event_id: str = Field(..., description="Stable event identifier, e.g. evt_01...")
    call_index: int = Field(
        ..., ge=0, description="Sequential call position in the execution trace"
    )
    tool_name: str = Field(..., description="Name of the invoked tool")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Normalized tool arguments captured"
    )
    status: EventStatus = Field(
        default=EventStatus.SUCCESS,
        description="Call completion status reported by the runner",
    )
    tool_response: Any = Field(
        default=None, description="Response payload returned by the tool"
    )
    tool_error: str | None = Field(
        default=None, description="Error message if the tool call failed"
    )
    parent_event_id: str | None = Field(
        default=None, description="Optional parent event identifier"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_tags: dict[str, str] = Field(
        default_factory=dict,
        description="Contextual provenance tags supplied by the adapter",
    )
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="Pointers to raw logs or traces corroborating this event",
    )


class AdapterExecutionResult(BaseModel):
    """Result returned by an agent execution adapter for a single test case."""

    session_id: str = Field(..., description="Isolated execution session ID")
    execution_status: CaseExecutionStatus = Field(
        ..., description="Execution status for the case"
    )
    trace_completeness: TraceCompleteness = Field(
        default=TraceCompleteness.COMPLETE,
        description="Completeness indicator for the captured trace",
    )
    events: list[CapturedToolEvent] = Field(
        default_factory=list, description="List of captured tool-call events"
    )
    raw_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Original raw adapter trace preserved alongside normalized events",
    )
    adapter_capabilities: list[str] = Field(
        default_factory=list, description="Capabilities declared by the adapter"
    )
    error_message: str | None = Field(
        default=None, description="Error message if execution or collection failed"
    )


class ExecutionRequest(BaseModel):
    """Request payload to initiate a test run on an accepted suite version."""

    suite_id: str = Field(..., min_length=1, description="ID of the accepted suite")
    suite_version: int | None = Field(
        default=None,
        ge=1,
        description="Suite version to run. If omitted, uses the highest accepted version.",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Client idempotency key to prevent accidental duplicate runs",
    )
    deadline_seconds: int = Field(
        default=60, ge=1, le=600, description="Execution timeout per case in seconds"
    )
    repetitions: int = Field(
        default=1,
        ge=1,
        le=5,
        description=(
            "Runs per case (fresh fixture and agent session each). Repetitions measure agent "
            "variability; they are aggregated per case, not counted as new test cases."
        ),
    )
    evaluator_version: str = Field(
        default="c1-evaluator-v1.0", description="Evaluator engine version to freeze"
    )
    code_version: str | None = Field(
        default=None, description="Optional repository commit or code version"
    )
    adapter_override: str | None = Field(
        default=None,
        description="Optional adapter simulation mode for integration testing",
    )


class CaseExecutionDetail(BaseModel):
    """Detailed execution record and evaluation result for a single case in a run."""

    execution_id: str = Field(..., description="Unique case execution identifier")
    case_id: str = Field(..., description="Target candidate case identifier")
    attempt_number: int = Field(
        default=1, ge=1, description="Attempt number for this case execution"
    )
    session_id: str = Field(..., description="Fresh agent session identifier")
    readiness_status: CaseReadinessStatus = Field(...)
    execution_status: CaseExecutionStatus = Field(...)
    verdict: CorrectnessVerdict | None = Field(
        default=None,
        description="Evaluated correctness verdict: PASS, FAIL, or INCONCLUSIVE",
    )
    trace_completeness: TraceCompleteness = Field(
        default=TraceCompleteness.COMPLETE,
    )
    resolved_expectations: list[ExpectedToolCallSpec] = Field(
        default_factory=list,
        description="Frozen expectations with fixture values resolved before agent presentation",
    )
    agent_task_sent: AgentFacingTask | None = Field(
        default=None,
        description="Stripped agent task payload confirming no oracle data leaked",
    )
    captured_events: list[CapturedToolEvent] = Field(
        default_factory=list,
        description="Normalized tool call events captured from agent execution",
    )
    evidence_records: list[EvidenceRef] = Field(
        default_factory=list,
        description="Evidence pointers captured during fixture prep and execution",
    )
    raw_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw trace preserved from the adapter",
    )
    check_results: list[CheckLevelResult] = Field(
        default_factory=list,
        description="Check-level declarative evaluation results",
    )
    error_message: str | None = Field(
        default=None,
        description="Execution or setup error message if failed",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)


class RunSummary(BaseModel):
    """Summary counts and status for an execution run."""

    run_id: str
    project_id: str
    suite_id: str
    suite_version: int
    status: RunStatus
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    inconclusive_cases: int = 0
    error_cases: int = 0
    repetitions: int = 1
    repetition_summary: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-case outcomes over repetitions (runs, verdict counts, pass rate)",
    )
    execution_provenance: str | None = Field(
        default=None,
        description=(
            "LIVE_EXECUTION or SYNTHETIC_DEMO when the recorded case traces corroborate it; "
            "None while no case evidence exists"
        ),
    )
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunDetailResponse(BaseModel):
    """Complete detail of an execution run including case execution summaries."""

    summary: RunSummary
    effective_config: dict[str, Any]
    case_executions: list[CaseExecutionDetail] = Field(default_factory=list)
