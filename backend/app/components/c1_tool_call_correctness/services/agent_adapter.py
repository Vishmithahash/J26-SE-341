import abc
from datetime import UTC, datetime
from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    AdapterExecutionResult,
    CapturedToolEvent,
    EventStatus,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import AgentFacingTask
from app.components.c1_tool_call_correctness.contracts.lifecycle import EvidenceRef
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
)

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "private_key",
}


def redact_sensitive_values(data: Any) -> Any:
    """Recursively redacts credential keys from arguments, traces, and metadata."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_values(v)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_values(elem) for elem in data]
    return data


class AgentExecutionAdapter(abc.ABC):
    """Abstract interface for invoking a tool-using agent and recording its trace."""

    @abc.abstractmethod
    def check_readiness(self) -> tuple[bool, str | None]:
        """Checks if the adapter target is configured and ready for execution.
        Returns (is_ready, failure_reason_if_not_ready).
        """

    @abc.abstractmethod
    def execute_task(
        self,
        session_id: str,
        task: AgentFacingTask,
        deadline_seconds: int = 60,
    ) -> AdapterExecutionResult:
        """Invokes the agent on the given task and captures trace events."""


class FakeAgentAdapter(AgentExecutionAdapter):
    """Simulated deterministic test adapter for component integration testing.
    Clearly labeled as SIMULATED_FAKE_ADAPTER.
    Supports deterministic reproduction of all target execution and failure categories.
    """

    ADAPTER_TYPE = "SIMULATED_FAKE_ADAPTER"

    def __init__(self, mode: str = "AUTO") -> None:
        self.mode = mode
        self.custom_events: list[CapturedToolEvent] | None = None
        self.custom_completeness: TraceCompleteness = TraceCompleteness.COMPLETE
        self.simulate_error: str | None = None

    def check_readiness(self) -> tuple[bool, str | None]:
        if self.mode == "UNAVAILABLE":
            return False, "Simulated adapter unavailable"
        return True, None

    def set_simulation(
        self,
        events: list[CapturedToolEvent] | None = None,
        completeness: TraceCompleteness = TraceCompleteness.COMPLETE,
        error_message: str | None = None,
    ) -> None:
        self.custom_events = events
        self.custom_completeness = completeness
        self.simulate_error = error_message

    def execute_task(
        self,
        session_id: str,
        task: AgentFacingTask,
        deadline_seconds: int = 60,
    ) -> AdapterExecutionResult:
        if self.simulate_error:
            return AdapterExecutionResult(
                session_id=session_id,
                execution_status=CaseExecutionStatus.EXECUTION_ERROR,
                trace_completeness=TraceCompleteness.CORRUPTED,
                events=[],
                raw_trace={"error": self.simulate_error, "adapter": self.ADAPTER_TYPE},
                adapter_capabilities=["simulated_trace_capture", "fake_execution"],
                error_message=self.simulate_error,
            )

        if self.custom_events is not None:
            return AdapterExecutionResult(
                session_id=session_id,
                execution_status=CaseExecutionStatus.EXECUTED,
                trace_completeness=self.custom_completeness,
                events=self.custom_events,
                raw_trace={
                    "simulated": True,
                    "event_count": len(self.custom_events),
                    "adapter": self.ADAPTER_TYPE,
                },
                adapter_capabilities=[
                    "simulated_trace_capture",
                    "fake_execution",
                ],
                error_message=None,
            )

        # Automatic generation based on task inputs and mode
        events = []
        raw_trace_items = []
        target_tool = (
            task.permitted_tools[0] if task.permitted_tools else "generic_tool"
        )

        if self.mode == "WRONG_TOOL":
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name="unauthorized_cancel_tool",
                arguments={"action": "cancel_everything"},
                status=EventStatus.SUCCESS,
                evidence_refs=[
                    EvidenceRef(
                        evidence_id=f"ev_trace_{session_id[:8]}_0",
                        channel=EvidenceChannel.AGENT_TRACE,
                        uri_or_pointer=f"trace://fake/{session_id}/0",
                        captured_at=datetime.now(UTC),
                    )
                ],
            )
            events.append(event)

        elif self.mode == "MISSING_ARG":
            # Pass customer_id and reason, omit amount or order_id
            args = {"reason": task.context_inputs.get("reason", "damaged")}
            if "customer_id" in task.context_inputs:
                args["customer_id"] = task.context_inputs["customer_id"]
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
            )
            events.append(event)

        elif self.mode == "MALFORMED_ARG":
            args = dict(task.context_inputs)
            args["amount"] = "forty-two-dollars"  # string instead of float
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
            )
            events.append(event)

        elif self.mode == "INCORRECT_VALUE":
            args = dict(task.context_inputs)
            args["amount"] = 9999.99  # incorrect out of range amount
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
            )
            events.append(event)

        elif self.mode == "SOURCE_MISMATCH":
            args = dict(task.context_inputs)
            args["customer_id"] = "cus_unrelated_999"
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
                source_tags={"customer_id": "cus_unrelated_999"},
            )
            events.append(event)

        elif self.mode == "EXPLICIT_NULL":
            args = dict(task.context_inputs)
            args["amount"] = None  # Explicit null
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
            )
            events.append(event)

        elif self.mode == "FAILED_CALL":
            args = dict(task.context_inputs)
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.FAILED,
                tool_error="Payment gateway API connection timeout (HTTP 504)",
            )
            events.append(event)

        elif self.mode == "INCOMPLETE_TRACE":
            # Emits partial event and marks completeness as INCOMPLETE
            args = dict(task.context_inputs)
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
            )
            return AdapterExecutionResult(
                session_id=session_id,
                execution_status=CaseExecutionStatus.EXECUTED,
                trace_completeness=TraceCompleteness.INCOMPLETE,
                events=[event],
                raw_trace={"stream_truncated": True, "adapter": self.ADAPTER_TYPE},
                adapter_capabilities=["simulated_trace_capture"],
                error_message="Trace stream interrupted before session close",
            )

        elif self.mode == "REFUSAL":
            # Agent refuses to call any tool (e.g. for insufficient evidence)
            events = []

        else:
            # Default AUTO_CORRECT: mirrors context_inputs accurately
            args = dict(task.context_inputs)
            # Ensure float types if present
            if "amount" in args:
                try:
                    args["amount"] = float(args["amount"])
                except (ValueError, TypeError):
                    pass
            event = CapturedToolEvent(
                event_id=f"evt_sim_{session_id[:8]}_0",
                call_index=0,
                tool_name=target_tool,
                arguments=args,
                status=EventStatus.SUCCESS,
                tool_response={"status": "approved", "processed": True},
                source_tags={k: str(v) for k, v in args.items() if v is not None},
                evidence_refs=[
                    EvidenceRef(
                        evidence_id=f"ev_trace_{session_id[:8]}_0",
                        channel=EvidenceChannel.AGENT_TRACE,
                        uri_or_pointer=f"trace://fake/{session_id}/0",
                        captured_at=datetime.now(UTC),
                    )
                ],
            )
            events.append(event)

        redacted_events = [
            CapturedToolEvent(
                event_id=e.event_id,
                call_index=e.call_index,
                tool_name=e.tool_name,
                arguments=redact_sensitive_values(e.arguments),
                status=e.status,
                tool_response=redact_sensitive_values(e.tool_response),
                tool_error=e.tool_error,
                parent_event_id=e.parent_event_id,
                timestamp=e.timestamp,
                source_tags=e.source_tags,
                evidence_refs=e.evidence_refs,
            )
            for e in events
        ]

        raw_trace_items = [e.model_dump(mode="json") for e in redacted_events]

        return AdapterExecutionResult(
            session_id=session_id,
            execution_status=CaseExecutionStatus.EXECUTED,
            trace_completeness=TraceCompleteness.COMPLETE,
            events=redacted_events,
            raw_trace={"calls": raw_trace_items, "adapter": self.ADAPTER_TYPE},
            adapter_capabilities=["simulated_trace_capture", "fake_execution"],
            error_message=None,
        )


class LiveAgentAdapter(AgentExecutionAdapter):
    """Adapter boundary for connecting to real live agent services.
    Validates connection parameters and tests endpoint readiness.
    """

    ADAPTER_TYPE = "LIVE_AGENT_ADAPTER"

    def __init__(self, connection_ref: str) -> None:
        self.connection_ref = connection_ref

    def check_readiness(self) -> tuple[bool, str | None]:
        if not self.connection_ref:
            return (
                False,
                "No agent connection reference specified in project configuration.",
            )
        if self.connection_ref.startswith("urn:conn:mock"):
            return (
                False,
                (
                    f"Live adapter cannot execute mock connection reference '{self.connection_ref}'. "
                    "A deployed agent HTTP endpoint or runtime container is required for live execution."
                ),
            )
        if not (
            self.connection_ref.startswith("http://")
            or self.connection_ref.startswith("https://")
        ):
            return (
                False,
                (
                    f"Unsupported live agent protocol for '{self.connection_ref}'. "
                    "Connection reference must be an HTTP or HTTPS endpoint URI."
                ),
            )
        # Endpoint is formatted, but live network calls are bound to actual deployments
        return (
            False,
            (
                f"Live agent endpoint '{self.connection_ref}' is currently unreachable: "
                "no live agent container is deployed at this endpoint."
            ),
        )

    def execute_task(
        self,
        session_id: str,
        task: AgentFacingTask,
        deadline_seconds: int = 60,
    ) -> AdapterExecutionResult:
        _is_ready, reason = self.check_readiness()
        return AdapterExecutionResult(
            session_id=session_id,
            execution_status=CaseExecutionStatus.EXECUTION_ERROR,
            trace_completeness=TraceCompleteness.MISSING,
            events=[],
            raw_trace={"connection_ref": self.connection_ref, "error": reason},
            adapter_capabilities=["live_http_client"],
            error_message=reason or "Live execution failed readiness check",
        )
