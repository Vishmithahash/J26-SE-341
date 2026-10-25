"""Live C1 execution against NexaCart's own LLM agent through the external QA harness.

Component: C1 - Explainable Tool-Call Correctness Testing

Per case: a fresh NexaCart fixture is created (``POST /qa/harness/fixtures``), the case task is
rendered with customer-visible fixture values and sent as the ONLY input to NexaCart's agent
(``POST /qa/harness/fixtures/{id}/agent-runs``), and the persisted tool calls NexaCart reports are
normalised into C1 events. Expected values are resolved from the real fixture context before the
agent runs. Nothing is simulated: when NexaCart, the harness or the agent's LLM provider fail, the
case is an execution error (no correctness verdict), never a fabricated trace.
"""

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
from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    FixturePreparationPlan,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import EvidenceRef
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
)
from app.components.c1_tool_call_correctness.examples.nexacart_live import (
    NEXACART_CUSTOMER_RECORDS,
    NEXACART_LIVE_FIXTURE_RECORD,
    NEXACART_REQUEST_RECORD,
)
from app.components.c1_tool_call_correctness.services.agent_adapter import (
    AgentExecutionAdapter,
    redact_sensitive_values,
)
from app.components.c1_tool_call_correctness.services.fixture_service import (
    SyntheticFixtureService,
)
from app.components.c1_tool_call_correctness.services.nexacart_live_generator import (
    render_task_prompt,
)
from app.shared.integration.adapters import LiveNexaCartTargetAdapter

# Failures of the agent's LLM provider are infrastructure errors, not agent tool-call behaviour.
INFRASTRUCTURE_AGENT_ERRORS = frozenset({"LLM_PROVIDER_ERROR"})


class NexaCartHarnessFixtureService(SyntheticFixtureService):
    """Prepares real NexaCart fixtures; the record ``fixture`` is NexaCart's reported context."""

    def __init__(self, target: LiveNexaCartTargetAdapter) -> None:
        super().__init__()
        self.target = target
        self.last_error: str | None = None

    def prepare_fixture(
        self,
        session_id: str,
        fixture_plan: FixturePreparationPlan,
    ) -> tuple[bool, dict[str, Any], list[EvidenceRef]]:
        self.last_error = None
        definition = (fixture_plan.starting_conditions or {}).get("nexacart_fixture")
        if not isinstance(definition, dict):
            self.last_error = "The case has no NexaCart fixture definition."
            return False, {}, []
        try:
            snapshot = self.target.prepare_fixture(
                session_id, {"nexacart_fixture": definition}
            )
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"NexaCart fixture creation failed: {exc}"
            return False, {}, []

        prepared = self.target.prepared_fixture(session_id) or {}
        fixture_id = str(prepared.get("fixture_id", ""))
        context = prepared.get("context") or {}
        order_numbers = [
            o["orderNumber"]
            for o in (context.get("orders") or {}).values()
            if o.get("orderNumber")
        ]
        if context.get("orderNumber"):
            order_numbers.append(context["orderNumber"])
        session_data = {
            NEXACART_LIVE_FIXTURE_RECORD: context,
            # The fixture customer is new, so these are all the orders the customer owns.
            NEXACART_CUSTOMER_RECORDS: {"orderNumbers": order_numbers},
        }
        self._session_stores[session_id] = session_data
        orders = sorted((context.get("orders") or {}).keys())
        products = sorted((context.get("products") or {}).keys())
        evidence = EvidenceRef(
            evidence_id=f"ev_nxc_fixture_{fixture_id[:8]}",
            channel=EvidenceChannel.AUT_DATABASE_DIFF,
            uri_or_pointer=f"nexacart://qa/harness/fixtures/{fixture_id}/snapshot",
            checksum=snapshot.fingerprint,
            summary=(
                f"Real NexaCart fixture {fixture_id} for customer {context.get('customerId')}: "
                f"orders {orders or '-'}, products {products or '-'}, cart version "
                f"{context.get('cartVersion')}. BEFORE snapshot fingerprint recorded."
            ),
        )
        return True, session_data, [evidence]

    def reset_session(self, session_id: str) -> None:
        super().reset_session(session_id)
        # Records stay in NexaCart as evidence; the harness only forgets the fixture.
        self.target.cleanup_fixture(session_id)


class NexaCartLiveAgentAdapter(AgentExecutionAdapter):
    """Runs a C1 case with NexaCart's real customer agent (provider/model reported by NexaCart)."""

    ADAPTER_TYPE = "NEXACART_LIVE_AGENT_ADAPTER"
    # Outcomes the execution service retries once on a fresh fixture (never agent behaviour).
    RETRYABLE_OUTCOMES = INFRASTRUCTURE_AGENT_ERRORS

    def __init__(self, target: LiveNexaCartTargetAdapter | None = None) -> None:
        self.target = target or LiveNexaCartTargetAdapter()
        self.fixture_service = NexaCartHarnessFixtureService(self.target)
        self.capabilities: dict[str, Any] | None = None

    @classmethod
    def for_base_url(cls, base_url: str) -> "NexaCartLiveAgentAdapter":
        """Adapter for another local NexaCart instance (same QA admin credentials from settings)."""
        from app.config import get_settings
        from app.shared.aut.nexacart import NexaCartHarnessClient

        settings = get_settings()
        client = NexaCartHarnessClient(
            base_url=base_url,
            admin_email=settings.nexacart_qa_admin_email,
            admin_password=settings.nexacart_qa_admin_password.get_secret_value(),
            agent_run_timeout_seconds=settings.nexacart_agent_run_timeout_seconds,
        )
        return cls(LiveNexaCartTargetAdapter(client=client))

    def check_readiness(self) -> tuple[bool, str | None]:
        status, reasons = self.target.check_readiness()
        if status.value != "READY":
            return False, " | ".join(reasons) or "Live NexaCart target is not ready."
        try:
            self.capabilities = self.target.client.get_capabilities()
        except Exception as exc:  # noqa: BLE001
            return False, f"NexaCart harness capabilities unavailable: {exc}"
        return True, None

    def describe(self) -> dict[str, Any]:
        """Execution provenance recorded in the run's effective configuration."""
        caps = self.capabilities or {}
        return {
            "application": "NexaCart",
            "base_url": getattr(self.target, "base_url", None),
            "harness_version": caps.get("harnessVersion"),
            "agent": caps.get("agent") or {},
            "is_live_execution": True,
        }

    def prepare_task(
        self, task: AgentFacingTask, session_data: dict[str, Any]
    ) -> tuple[AgentFacingTask, str | None]:
        """Render customer-visible fixture values into the task; returns (task, error)."""
        prompt, unresolved = render_task_prompt(task.task_prompt, session_data)
        if unresolved:
            return task, (
                f"Task placeholders could not be resolved from the NexaCart fixture: {unresolved}."
            )
        # Customer-stated facts (amount, quantity, limit) are a source record for expectations.
        session_data[NEXACART_REQUEST_RECORD] = dict(task.context_inputs)
        tools = [t.get("name") for t in (self.capabilities or {}).get("tools", [])]
        return (
            task.model_copy(
                update={
                    "task_prompt": prompt,
                    # The agent always has NexaCart's full tool registry; QA does not narrow it.
                    "permitted_tools": [t for t in tools if t] or task.permitted_tools,
                }
            ),
            None,
        )

    def execute_task(
        self,
        session_id: str,
        task: AgentFacingTask,
        deadline_seconds: int = 60,
    ) -> AdapterExecutionResult:
        base_trace: dict[str, Any] = {
            "adapter": self.ADAPTER_TYPE,
            "is_live_execution": True,
            "simulated": False,
            "application": "NexaCart",
            "task_sent": task.task_prompt,
            "deadline_note": (
                "NexaCart enforces its own agent budgets (steps, tool calls, run timeout); "
                f"the requested deadline of {deadline_seconds}s is informational."
            ),
        }
        try:
            trace = self.target.execute_session(
                namespace=session_id,
                task_prompt=task.task_prompt,
                permitted_tools=[],
                trial_role="C1",
            )
        except Exception as exc:  # noqa: BLE001
            return AdapterExecutionResult(
                session_id=session_id,
                execution_status=CaseExecutionStatus.EXECUTION_ERROR,
                trace_completeness=TraceCompleteness.MISSING,
                raw_trace={**base_trace, "error": str(exc)},
                adapter_capabilities=["nexacart_qa_harness"],
                error_message=f"Live NexaCart agent run failed: {exc}",
            )

        meta = trace.aut_metadata or {}
        run_id = meta.get("agent_run_id") or "unknown"
        events = [
            CapturedToolEvent(
                event_id=ev.event_id,
                call_index=ev.call_index,
                tool_name=ev.tool_name,
                arguments=redact_sensitive_values(ev.arguments),
                status=EventStatus.SUCCESS if ev.success else EventStatus.FAILED,
                tool_response=redact_sensitive_values(ev.output),
                tool_error=ev.error,
                timestamp=ev.timestamp_utc,
                source_tags={
                    "agent_run_id": str(run_id),
                    "nexacart_tool_call_id": ev.event_id.removeprefix("nxc-call-"),
                    "state_changing_effect": str(ev.side_effect_occurred).lower(),
                },
                evidence_refs=[
                    EvidenceRef(
                        evidence_id=f"ev_{ev.event_id}",
                        channel=EvidenceChannel.TOOL_CALL_LOG,
                        uri_or_pointer=f"nexacart://agent-runs/{run_id}/tool-calls/{ev.call_index}",
                        summary=(
                            f"NexaCart agent_tool_calls #{ev.call_index} {ev.tool_name} "
                            f"{'SUCCEEDED' if ev.success else 'FAILED'}"
                            + (f": {ev.error}" if ev.error else "")
                        ),
                    )
                ],
            )
            for ev in sorted(trace.tool_events, key=lambda e: e.call_index)
        ]
        raw_trace = {
            **base_trace,
            "agent_run_id": meta.get("agent_run_id"),
            "agent_status": meta.get("agent_status"),
            "agent_provider": meta.get("agent_provider"),
            "agent_model": meta.get("agent_model"),
            "final_answer": meta.get("final_answer"),
            "agent_error": meta.get("agent_error"),
            "caller_outcome": trace.caller_outcome,
            "qa_run_id": meta.get("qa_run_id"),
            "nexacart_fixture_id": meta.get("fixture_id"),
            "fixture_context": meta.get("fixture_context"),
            "duration_ms": meta.get("duration_ms"),
            "harness_version": (self.capabilities or {}).get("harnessVersion"),
            "observation_errors": meta.get("observation_errors") or [],
            "before_snapshot": trace.initial_state.state,
            "after_snapshot": trace.final_state.state,
            "state_snapshots_after_calls": len(
                meta.get("intermediate_snapshots") or []
            ),
            "calls": [e.model_dump(mode="json") for e in events],
        }

        if trace.caller_outcome in INFRASTRUCTURE_AGENT_ERRORS:
            message = (meta.get("agent_error") or {}).get("message", "")
            return AdapterExecutionResult(
                session_id=session_id,
                execution_status=CaseExecutionStatus.EXECUTION_ERROR,
                trace_completeness=TraceCompleteness.INCOMPLETE,
                events=events,
                raw_trace=raw_trace,
                adapter_capabilities=["nexacart_qa_harness"],
                error_message=(
                    f"NexaCart agent run ended with {trace.caller_outcome}: {message}. "
                    "An LLM provider failure is not judged as tool-call behaviour."
                ).strip(),
            )

        complete = trace.is_complete and trace.caller_outcome == "SUCCESS"
        return AdapterExecutionResult(
            session_id=session_id,
            execution_status=CaseExecutionStatus.EXECUTED,
            trace_completeness=TraceCompleteness.COMPLETE
            if complete
            else TraceCompleteness.INCOMPLETE,
            events=events,
            raw_trace=raw_trace,
            adapter_capabilities=[
                "nexacart_qa_harness",
                "persisted_tool_calls",
                "before_after_snapshots",
            ],
            error_message=None
            if complete
            else (
                f"NexaCart agent run did not complete normally ({trace.caller_outcome}); "
                "absent calls cannot be confirmed."
            ),
        )
