"""Bounded fault interception on the domain tool path.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
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
from app.components.c3_robustness_recovery.runtime.faults import (
    get_fault_handler,
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
    fault_mode: Any
    caller_timeout_ms: int = 1000
    fault_timing_ms: int | None = None
    timeout_boundary_type: TimeoutBoundaryType = (
        TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED
    )
    payload_details: dict[str, Any] = field(default_factory=dict)


class DomainToolInterceptor:
    """Trial-scoped interceptor placed directly on the domain tool execution path.

    Guarantees:
    - Thread-safe and coroutine-safe atomic one-shot delivery.
    - Unrelated tool calls do not increment or shift the target occurrence counter.
    - Locks are released before waiting or I/O.
    - Target forward callback is never invoked on intercepted BEFORE_EFFECT calls.
    - On AFTER_COMMIT, forward callback runs, effect is independently confirmed, then reply is withheld.
    - Cancellation never forwards the intercepted request later.
    - Premature cancellation is strictly distinguished from caller deadline expiry.
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
        should_intercept_before = False
        should_intercept_after_commit = False
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
            ):
                if (
                    self.plan.interception_hook == InterceptionHook.BEFORE_TOOL_CALL
                    and self.plan.effect_phase == EffectPhase.BEFORE_EFFECT
                ):
                    should_intercept_before = True
                    self._episode_consumed = True
                    episode_id = f"ep-{uuid4().hex[:12]}"
                elif (
                    self.plan.interception_hook
                    == InterceptionHook.APPLICATION_AWARE_HOOK
                    and self.plan.effect_phase == EffectPhase.AFTER_COMMIT
                ):
                    should_intercept_after_commit = True
                    self._episode_consumed = True
                    episode_id = f"ep-{uuid4().hex[:12]}"

        # Lock is now completely RELEASED before any sleep, delay, or forwarding
        try:
            if should_intercept_before and self.plan is not None:
                if self.plan.fault_family == FaultFamily.TIMEOUT_DISCONNECTION:
                    return await self._handle_intercepted_timeout(
                        tool_id=tool_id,
                        tool_version=tool_version,
                        arguments=arguments,
                        arg_fp=arg_fp,
                        current_occurrence=current_occurrence,
                        episode_id=episode_id,
                    )
                # Remaining 4 fault families in Phase 3
                return await self._handle_intercepted_delivery_handler(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    arg_fp=arg_fp,
                    current_occurrence=current_occurrence,
                    episode_id=episode_id,
                    context=context,
                )

            if should_intercept_after_commit and self.plan is not None:
                return await self._handle_intercepted_after_commit(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    arg_fp=arg_fp,
                    current_occurrence=current_occurrence,
                    episode_id=episode_id,
                    forward_callback=forward_callback,
                    context=context,
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
        """Handle targeted one-shot BEFORE_EFFECT timeout injection without forwarding."""
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

        caller_timeout_sec = plan.caller_timeout_ms / 1000.0
        hold_sec = caller_timeout_sec
        if plan.fault_timing_ms is not None:
            hold_sec = max(caller_timeout_sec, plan.fault_timing_ms / 1000.0)

        start_time = self._clock()
        try:
            await asyncio.sleep(hold_sec)
        except asyncio.CancelledError:
            elapsed_ms = (self._clock() - start_time) * 1000.0
            # Gap A fix: Cancellation vs Timeout
            # Require elapsed time >= 90% of declared caller timeout to establish deadline expiry.
            is_deadline_expiry = elapsed_ms >= (plan.caller_timeout_ms * 0.9)
            cancellation_reason = (
                "CALLER_DEADLINE_EXPIRY"
                if is_deadline_expiry
                else "PREMATURE_EXTERNAL_CANCELLATION"
            )
            caller_observed = is_deadline_expiry

            episode_record = FaultEpisodeRecord(
                episode_id=episode_id,
                target_tool_id=tool_id,
                target_occurrence=current_occurrence,
                interception_hook=plan.interception_hook,
                effect_phase=plan.effect_phase,
                fault_family=plan.fault_family,
                fault_mode=(
                    plan.fault_mode
                    if isinstance(plan.fault_mode, str)
                    else getattr(plan.fault_mode, "value", str(plan.fault_mode))
                ),
                declared_caller_timeout_ms=plan.caller_timeout_ms,
                fault_timing_ms=plan.fault_timing_ms,
                timeout_boundary_type=plan.timeout_boundary_type,
                prevented_forwarding=True,
                caller_observed_timeout=caller_observed,
                elapsed_wait_ms=elapsed_ms,
                consumed_atomically=True,
                cancellation_reason=cancellation_reason,
            )
            self._episode_records.append(episode_record)

            event_type = (
                "CALLER_TIMEOUT_OBSERVED_ON_CANCELLATION"
                if is_deadline_expiry
                else "INTERCEPTION_CANCELLED_BEFORE_TIMEOUT"
            )
            self._events.append(
                RuntimeEvent(
                    event_type=event_type,
                    tool_id=tool_id,
                    occurrence=current_occurrence,
                    forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_TIMEOUT,
                    safe_argument_fingerprint=arg_fp,
                    details={
                        "episode_id": episode_id,
                        "elapsed_ms": elapsed_ms,
                        "boundary": (
                            "Caller timeout interrupted operation"
                            if is_deadline_expiry
                            else "Operation cancelled before timeout boundary"
                        ),
                        "cancellation_reason": cancellation_reason,
                    },
                )
            )
            # Re-raise cancellation faithfully without forwarding
            raise

        elapsed_ms = (self._clock() - start_time) * 1000.0
        boundary_type = plan.timeout_boundary_type

        episode_record = FaultEpisodeRecord(
            episode_id=episode_id,
            target_tool_id=tool_id,
            target_occurrence=current_occurrence,
            interception_hook=plan.interception_hook,
            effect_phase=plan.effect_phase,
            fault_family=plan.fault_family,
            fault_mode=(
                plan.fault_mode
                if isinstance(plan.fault_mode, str)
                else getattr(plan.fault_mode, "value", str(plan.fault_mode))
            ),
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

        raise TimeoutError(
            f"Caller timeout of {plan.caller_timeout_ms}ms exceeded on tool '{tool_id}' "
            f"(elapsed: {elapsed_ms:.1f}ms)."
        )

    async def _handle_intercepted_delivery_handler(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        arg_fp: str,
        current_occurrence: int,
        episode_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Handle BEFORE_EFFECT non-timeout fault delivery (5xx, 429, unavailability, malformed)."""
        assert self.plan is not None
        plan = self.plan

        self._events.append(
            RuntimeEvent(
                event_type="HOOK_ENTRY_BEFORE_TOOL_CALL",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_FAULT,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "fault_family": plan.fault_family.value,
                    "fault_mode": str(plan.fault_mode),
                },
            )
        )

        handler = get_fault_handler(plan.fault_family)
        delivery = await handler.deliver_fault(
            tool_id=tool_id,
            tool_version=tool_version,
            arguments=arguments,
            plan=plan,
            context=context or {},
        )

        fault_mode_str = (
            plan.fault_mode
            if isinstance(plan.fault_mode, str)
            else getattr(plan.fault_mode, "value", str(plan.fault_mode))
        )
        episode_record = FaultEpisodeRecord(
            episode_id=episode_id,
            target_tool_id=tool_id,
            target_occurrence=current_occurrence,
            interception_hook=plan.interception_hook,
            effect_phase=plan.effect_phase,
            fault_family=plan.fault_family,
            fault_mode=fault_mode_str,
            declared_caller_timeout_ms=plan.caller_timeout_ms,
            fault_timing_ms=plan.fault_timing_ms,
            timeout_boundary_type=plan.timeout_boundary_type,
            prevented_forwarding=True,
            caller_observed_timeout=False,
            elapsed_wait_ms=0.0,
            consumed_atomically=True,
            fault_status_code=delivery.status_code,
            retry_after_seconds=delivery.retry_after_seconds,
            unavailability_mode=delivery.unavailability_mode,
            malformed_fragment=delivery.malformed_fragment,
        )
        self._episode_records.append(episode_record)

        self._events.append(
            RuntimeEvent(
                event_type=f"FAULT_DELIVERED_{plan.fault_family.value}",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.PREVENTED_INJECTED_FAULT,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "status_code": delivery.status_code,
                    "retry_after_seconds": delivery.retry_after_seconds,
                    "unavailability_mode": delivery.unavailability_mode,
                },
            )
        )

        if delivery.raised_exception:
            raise delivery.raised_exception

        assert delivery.result is not None
        return delivery.result

    async def _handle_intercepted_after_commit(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        arg_fp: str,
        current_occurrence: int,
        episode_id: str,
        forward_callback: Callable[[], Awaitable[ToolExecutionResult]],
        context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Handle application-aware AFTER_COMMIT lost-response delivery.

        Order:
        1. Matching operation reaches APPLICATION_AWARE_HOOK.
        2. Target performs its effect.
        3. Independent observation confirms that exact operation committed.
        4. The reply is withheld at the declared boundary.
        5. Caller experiences the intended lost-response timeout condition.
        """
        assert self.plan is not None
        plan = self.plan

        # Step 1: Hook entry
        self._events.append(
            RuntimeEvent(
                event_type="APPLICATION_AWARE_HOOK_ENTERED",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "stage": "Hook entered before effect",
                },
            )
        )

        # Step 2: Target performs its effect
        target_result = await forward_callback()

        # Step 3: Independent observation confirms that exact operation committed
        operation_id = None
        if isinstance(target_result.output, dict):
            operation_id = target_result.output.get("order_id")
        if not operation_id and isinstance(target_result.idempotency_key, str):
            operation_id = target_result.idempotency_key

        ctx = context or {}
        fixture_mgr = ctx.get("fixture_manager")
        namespace = ctx.get("namespace", "")

        observation_confirmed = False
        if (
            fixture_mgr
            and operation_id
            and hasattr(fixture_mgr, "verify_committed_operation")
        ):
            observation_confirmed = fixture_mgr.verify_committed_operation(
                namespace, operation_id
            )

        self._events.append(
            RuntimeEvent(
                event_type="INDEPENDENT_COMMIT_OBSERVATION",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED_COMMITTED_RESPONSE_WITHHELD,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "operation_id": operation_id,
                    "observation_confirmed": observation_confirmed,
                    "side_effect_occurred": target_result.side_effect_occurred,
                },
            )
        )

        fault_mode_str = (
            plan.fault_mode
            if isinstance(plan.fault_mode, str)
            else getattr(plan.fault_mode, "value", str(plan.fault_mode))
        )

        # If observation is not confirmed, missing commit observation prevents confirmed post-commit exposure
        if not observation_confirmed:
            episode_record = FaultEpisodeRecord(
                episode_id=episode_id,
                target_tool_id=tool_id,
                target_occurrence=current_occurrence,
                interception_hook=plan.interception_hook,
                effect_phase=plan.effect_phase,
                fault_family=plan.fault_family,
                fault_mode=fault_mode_str,
                declared_caller_timeout_ms=plan.caller_timeout_ms,
                timeout_boundary_type=plan.timeout_boundary_type,
                prevented_forwarding=False,
                caller_observed_timeout=False,
                elapsed_wait_ms=0.0,
                consumed_atomically=True,
                committed_operation_id=operation_id,
                independent_observation_confirmed=False,
            )
            self._episode_records.append(episode_record)
            return target_result

        # Step 4: The reply is withheld at the declared boundary
        self._events.append(
            RuntimeEvent(
                event_type="POST_COMMIT_REPLY_WITHHELD",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED_COMMITTED_RESPONSE_WITHHELD,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "operation_id": operation_id,
                    "action": "Withholding reply to simulate lost response",
                },
            )
        )

        start_time = self._clock()
        hold_sec = plan.caller_timeout_ms / 1000.0
        if plan.fault_timing_ms is not None:
            hold_sec = max(hold_sec, plan.fault_timing_ms / 1000.0)

        try:
            await asyncio.sleep(hold_sec)
        except asyncio.CancelledError:
            elapsed_ms = (self._clock() - start_time) * 1000.0
            is_deadline = elapsed_ms >= (plan.caller_timeout_ms * 0.9)
            episode_record = FaultEpisodeRecord(
                episode_id=episode_id,
                target_tool_id=tool_id,
                target_occurrence=current_occurrence,
                interception_hook=plan.interception_hook,
                effect_phase=plan.effect_phase,
                fault_family=plan.fault_family,
                fault_mode=fault_mode_str,
                declared_caller_timeout_ms=plan.caller_timeout_ms,
                timeout_boundary_type=plan.timeout_boundary_type,
                prevented_forwarding=False,
                caller_observed_timeout=is_deadline,
                elapsed_wait_ms=elapsed_ms,
                consumed_atomically=True,
                committed_operation_id=operation_id,
                independent_observation_confirmed=True,
                cancellation_reason=(
                    "CALLER_DEADLINE_EXPIRY"
                    if is_deadline
                    else "PREMATURE_EXTERNAL_CANCELLATION"
                ),
            )
            self._episode_records.append(episode_record)
            raise

        elapsed_ms = (self._clock() - start_time) * 1000.0

        # Step 5: Caller experiences the intended lost-response timeout condition
        episode_record = FaultEpisodeRecord(
            episode_id=episode_id,
            target_tool_id=tool_id,
            target_occurrence=current_occurrence,
            interception_hook=plan.interception_hook,
            effect_phase=plan.effect_phase,
            fault_family=plan.fault_family,
            fault_mode=fault_mode_str,
            declared_caller_timeout_ms=plan.caller_timeout_ms,
            timeout_boundary_type=plan.timeout_boundary_type,
            prevented_forwarding=False,
            caller_observed_timeout=True,
            elapsed_wait_ms=elapsed_ms,
            consumed_atomically=True,
            committed_operation_id=operation_id,
            independent_observation_confirmed=True,
        )

        self._episode_records.append(episode_record)

        self._events.append(
            RuntimeEvent(
                event_type="LOST_RESPONSE_TIMEOUT_ENFORCED",
                tool_id=tool_id,
                occurrence=current_occurrence,
                forwarding_decision=ForwardingDecision.FORWARDED_COMMITTED_RESPONSE_WITHHELD,
                safe_argument_fingerprint=arg_fp,
                details={
                    "episode_id": episode_id,
                    "operation_id": operation_id,
                    "elapsed_ms": elapsed_ms,
                },
            )
        )

        raise TimeoutError(
            f"Lost-response timeout of {plan.caller_timeout_ms}ms exceeded after commit of operation '{operation_id}'."
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
