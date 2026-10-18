"""Bounded one-shot timeout interception on the domain tool path.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 2 - One-tool integration, matched trials, verified timeout exposure and safeguards.
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    TimeoutDisconnectionMode,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    ToolExecutionResult,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    FaultEpisodeRecord,
    ForwardingDecision,
    RuntimeEvent,
    TimeoutBoundaryType,
    compute_argument_fingerprint,
)


@dataclass(frozen=True)
class InterceptionPlan:
    """Interception plan configuring the exact targeted episode for a fault trial."""

    trial_id: str
    target_tool_id: str
    target_occurrence: int
    interception_hook: InterceptionHook
    effect_phase: EffectPhase
    fault_family: FaultFamily
    fault_mode: TimeoutDisconnectionMode
    caller_timeout_ms: int
    fault_timing_ms: int | None = None
    timeout_boundary_type: TimeoutBoundaryType = (
        TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED
    )


class DomainToolInterceptor:
    """Trial-scoped interceptor placed directly on the domain tool execution path.

    Guarantees:
    - Thread-safe and coroutine-safe atomic one-shot delivery.
    - Unrelated tool calls do not increment or shift the target occurrence counter.
    - Locks are released before waiting or I/O.
    - Target forward callback is never invoked on the intercepted call.
    - Cancellation never forwards the intercepted request later.
    - Subsequent calls pass through unhindered.
    """

    def __init__(
        self,
        trial_id: str,
        plan: InterceptionPlan | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.trial_id = trial_id
        self.plan = plan
        self._clock = clock

        self._lock = asyncio.Lock()
        self._tool_call_counts: dict[str, int] = defaultdict(int)
        self._episode_consumed = False
        self._is_closed = False

        # Recorded evidence during trial
        self._events: list[RuntimeEvent] = []
        self._episode_records: list[FaultEpisodeRecord] = []
        self._in_flight_count = 0

    @property
    def is_consumed(self) -> bool:
        return self._episode_consumed

    @property
    def events(self) -> list[RuntimeEvent]:
        return list(self._events)

    @property
    def episode_records(self) -> list[FaultEpisodeRecord]:
        return list(self._episode_records)

    def close(self) -> None:
        """Mark interceptor closed. New trial calls will be rejected."""
        self._is_closed = True

    async def intercept_call(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        forward_callback: Callable[[], Awaitable[ToolExecutionResult]],
        context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Intercept a domain tool invocation on behalf of the caller."""
        if self._is_closed:
            raise RuntimeError(
                f"Trial interceptor '{self.trial_id}' is closed and no longer accepting calls."
            )

        arg_fp = compute_argument_fingerprint(arguments)
        should_intercept = False
        current_occurrence = 0
        episode_id = ""

        # Atomic decision section - lock held ONLY for state inspection and counter increment
        async with self._lock:
            if self._is_closed:
                raise RuntimeError(
                    f"Trial interceptor '{self.trial_id}' was closed during dispatch."
                )

            self._in_flight_count += 1
            # Unrelated tool calls have their own independent counter
            self._tool_call_counts[tool_id] += 1
            current_occurrence = self._tool_call_counts[tool_id]

            if (
                self.plan is not None
                and not self._episode_consumed
                and tool_id == self.plan.target_tool_id
                and current_occurrence == self.plan.target_occurrence
                and self.plan.interception_hook == InterceptionHook.BEFORE_TOOL_CALL
                and self.plan.effect_phase == EffectPhase.BEFORE_EFFECT
            ):
                should_intercept = True
                self._episode_consumed = True
                episode_id = f"ep-{uuid4().hex[:12]}"

        # Lock is now completely RELEASED before any sleep, delay, or forwarding
        try:
            if should_intercept and self.plan is not None:
                return await self._handle_intercepted_timeout(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    arg_fp=arg_fp,
                    current_occurrence=current_occurrence,
                    episode_id=episode_id,
                )

            # Normal forward path: clean trial, non-targeted tool, or subsequent occurrence
            return await self._handle_forwarded_call(
                tool_id=tool_id,
                tool_version=tool_version,
                arguments=arguments,
                arg_fp=arg_fp,
                current_occurrence=current_occurrence,
                forward_callback=forward_callback,
            )
        finally:
            async with self._lock:
                self._in_flight_count = max(0, self._in_flight_count - 1)

    async def _handle_intercepted_timeout(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        arg_fp: str,
        current_occurrence: int,
        episode_id: str,
    ) -> ToolExecutionResult:
        """Handle the targeted one-shot timeout injection without forwarding."""
        assert self.plan is not None
        plan = self.plan

        hook_event = RuntimeEvent(
            event_type="HOOK_ENTRY_BEFORE_TOOL_CALL",
            tool_id=tool_id,
            occurrence=current_occurrence,
            forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_TIMEOUT,
            safe_argument_fingerprint=arg_fp,
            details={
                "episode_id": episode_id,
                "reason": "Targeted caller timeout fault injection",
                "declared_caller_timeout_ms": plan.caller_timeout_ms,
            },
        )
        self._events.append(hook_event)

        # Calculate bounded hold duration to reach caller-timeout boundary
        caller_timeout_sec = plan.caller_timeout_ms / 1000.0
        # For bounded hold: hold until caller timeout is reached
        hold_sec = caller_timeout_sec
        if plan.fault_timing_ms is not None:
            # If timing_ms is given, we hold up to timing_ms or caller_timeout
            hold_sec = max(caller_timeout_sec, plan.fault_timing_ms / 1000.0)

        start_time = self._clock()
        try:
            # Hold coroutine until caller timeout boundary is reached
            await asyncio.sleep(hold_sec)
        except asyncio.CancelledError:
            # If cancelled by caller (e.g., caller's own timeout mechanism timed out)
            elapsed_ms = (self._clock() - start_time) * 1000.0
            episode_record = FaultEpisodeRecord(
                episode_id=episode_id,
                target_tool_id=tool_id,
                target_occurrence=current_occurrence,
                interception_hook=plan.interception_hook,
                effect_phase=plan.effect_phase,
                fault_family=plan.fault_family,
                fault_mode=plan.fault_mode.value,
                declared_caller_timeout_ms=plan.caller_timeout_ms,
                fault_timing_ms=plan.fault_timing_ms,
                timeout_boundary_type=plan.timeout_boundary_type,
                prevented_forwarding=True,
                caller_observed_timeout=True,
                elapsed_wait_ms=elapsed_ms,
                consumed_atomically=True,
            )
            self._episode_records.append(episode_record)
            self._events.append(
                RuntimeEvent(
                    event_type="CALLER_TIMEOUT_OBSERVED_ON_CANCELLATION",
                    tool_id=tool_id,
                    occurrence=current_occurrence,
                    forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_TIMEOUT,
                    safe_argument_fingerprint=arg_fp,
                    details={
                        "episode_id": episode_id,
                        "elapsed_ms": elapsed_ms,
                        "boundary": "Caller timeout interrupted operation",
                    },
                )
            )
            # Critical: DO NOT forward the call; re-raise cancellation faithfully
            raise

        elapsed_ms = (self._clock() - start_time) * 1000.0
        boundary_type = plan.timeout_boundary_type

        # Record faithful episode evidence
        episode_record = FaultEpisodeRecord(
            episode_id=episode_id,
            target_tool_id=tool_id,
            target_occurrence=current_occurrence,
            interception_hook=plan.interception_hook,
            effect_phase=plan.effect_phase,
            fault_family=plan.fault_family,
            fault_mode=plan.fault_mode.value,
            declared_caller_timeout_ms=plan.caller_timeout_ms,
            fault_timing_ms=plan.fault_timing_ms,
            timeout_boundary_type=boundary_type,
            prevented_forwarding=True,
            caller_observed_timeout=True,
            elapsed_wait_ms=elapsed_ms,
            consumed_atomically=True,
        )
        self._episode_records.append(episode_record)

        self._events.append(
            RuntimeEvent(
                event_type="CALLER_TIMEOUT_EXCEEDED_ELAPSED",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_TIMEOUT,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "elapsed_ms": elapsed_ms,
                    "caller_timeout_ms": plan.caller_timeout_ms,
                },
            )
        )

        # Enforce caller timeout exception on the intercepted tool path
        raise TimeoutError(
            f"Caller timeout of {plan.caller_timeout_ms}ms exceeded on tool '{tool_id}' "
            f"(elapsed: {elapsed_ms:.1f}ms)."
        )

    async def _handle_forwarded_call(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        arg_fp: str,
        current_occurrence: int,
        forward_callback: Callable[[], Awaitable[ToolExecutionResult]],
    ) -> ToolExecutionResult:
        """Handle normal pass-through execution to the target tool."""
        self._events.append(
            RuntimeEvent(
                event_type="HOOK_ENTRY_FORWARDING",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED,
                safe_argument_fingerprint=arg_fp,
                details={
                    "status": "Forwarding to domain target",
                },
            )
        )

        start_time = self._clock()
        result = await forward_callback()
        elapsed_ms = (self._clock() - start_time) * 1000.0

        self._events.append(
            RuntimeEvent(
                event_type="TOOL_EXECUTION_COMPLETED",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED,
                safe_argument_fingerprint=arg_fp,
                details={
                    "success": result.success,
                    "side_effect_occurred": result.side_effect_occurred,
                    "latency_ms": elapsed_ms,
                },
            )
        )
        return result
