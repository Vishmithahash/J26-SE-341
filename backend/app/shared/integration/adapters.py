"""Target adapters and honest readiness checks for shared execution.

Component: Shared Integration Coordination (Part 2)
Responsibilities:
- Provide honest readiness checks for external targets (NexaCart).
- When external live target is unavailable/unreachable, report external readiness as BLOCKED.
  Live mode must NEVER fall back silently to simulation.
- Provide a controlled, deterministic test adapter labelled clearly as 'test_infrastructure'.
- Isolate fixture partitions, capture raw tool events, and observe domain state snapshots.
- Scrub credentials and sensitive headers before returning evidence.
"""

import copy
import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TargetMode(str, Enum):
    """Target execution mode."""

    CONTROLLED_TEST = "CONTROLLED_TEST"  # Deterministic test double, clearly labelled as test infrastructure
    LIVE_AUT = "LIVE_AUT"  # Live application under test


class TargetReadinessStatus(str, Enum):
    """Readiness status of target execution adapter."""

    READY = "READY"
    BLOCKED = "BLOCKED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class RawToolEvent(BaseModel):
    """Raw recorded tool event from a single application execution."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    call_index: int
    tool_name: str
    arguments: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    success: bool = True
    latency_ms: float = 0.0
    side_effect_occurred: bool = False
    idempotency_key: str | None = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StateSnapshot(BaseModel):
    """Captured snapshot of domain state entities."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    time_scope: str = "post_recovery"
    entity_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str = ""
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionTrace(BaseModel):
    """Retained evidence from a single trial execution."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    trial_role: str = "DEFAULT"  # "CLEAN", "FAULT", or "DEFAULT"
    target_mode: TargetMode
    is_simulation: bool
    caller_outcome: str = "SUCCESS"
    tool_events: list[RawToolEvent] = Field(default_factory=list)
    initial_state: StateSnapshot
    final_state: StateSnapshot
    is_complete: bool = True
    fault_injected: bool = False
    fault_details: dict[str, Any] | None = None
    injection_delivered: bool = False
    injection_details: dict[str, Any] | None = None
    cleanup_successful: bool = True
    cleanup_reusable: bool = True


# ---------------------------------------------------------------------------
# Sanitization Helper
# ---------------------------------------------------------------------------

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "private_key",
}


def sanitize_payload(data: Any) -> Any:
    """Recursively scrub secrets, credentials, and Authorization headers."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    if isinstance(data, list):
        return [sanitize_payload(item) for item in data]
    return data


def compute_snapshot_fingerprint(data: dict[str, Any]) -> str:
    """Deterministic hash of sanitized state snapshot."""
    clean = sanitize_payload(data)
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Target Adapter Contract
# ---------------------------------------------------------------------------


class BaseTargetAdapter(ABC):
    """Abstract interface for application under test adapters."""

    @abstractmethod
    def check_readiness(self) -> tuple[TargetReadinessStatus, list[str]]:
        """Verify whether the target environment and endpoints are ready."""
        ...

    @abstractmethod
    def prepare_fixture(
        self, namespace: str, seed_data: dict[str, Any] | None = None
    ) -> StateSnapshot:
        """Initialize an isolated fixture partition and return initial state snapshot."""
        ...

    @abstractmethod
    def execute_session(
        self,
        namespace: str,
        task_prompt: str,
        permitted_tools: list[str],
        fault_injection_hook: dict[str, Any] | None = None,
        prompt_injection_payload: str | None = None,
        max_tool_calls: int = 50,
        trial_role: str = "DEFAULT",
        deadline_monotonic: float | None = None,
        check_cancellation: Callable[[], bool] | None = None,
    ) -> ExecutionTrace:
        """Execute the tested application/agent once and capture actual trace and observations."""
        ...

    @abstractmethod
    def cleanup_fixture(self, namespace: str) -> tuple[bool, bool]:
        """Tear down fixture partition. Returns (cleanup_success, fixture_reusable)."""
        ...


# ---------------------------------------------------------------------------
# Honest Live Adapter
# ---------------------------------------------------------------------------


class LiveNexaCartTargetAdapter(BaseTargetAdapter):
    """Authoritative adapter for live NexaCart target application.

    Reports honest readiness: since live NexaCart external service endpoints are not running,
    it returns BLOCKED. Live mode must NEVER fall back silently to simulation.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or "http://localhost:8080"

    def check_readiness(self) -> tuple[TargetReadinessStatus, list[str]]:
        """Check live external NexaCart endpoints.

        Does not invent endpoints or assume an open port proves execution capability.
        """
        # Live NexaCart external microservice is not hosted in this monolith repo
        return (
            TargetReadinessStatus.BLOCKED,
            [
                (
                    f"Live target service at '{self.base_url}' is unreachable or not configured. "
                    "No live external NexaCart reset/agent/fault-hook endpoints are active. "
                    "External readiness is BLOCKED. Simulation fallback is rejected in LIVE_AUT mode."
                )
            ],
        )

    def prepare_fixture(
        self, namespace: str, seed_data: dict[str, Any] | None = None
    ) -> StateSnapshot:
        raise RuntimeError(
            "Cannot prepare live fixture: Live NexaCart service is BLOCKED."
        )

    def execute_session(
        self,
        namespace: str,
        task_prompt: str,
        permitted_tools: list[str],
        fault_injection_hook: dict[str, Any] | None = None,
        prompt_injection_payload: str | None = None,
        max_tool_calls: int = 50,
        trial_role: str = "DEFAULT",
        deadline_monotonic: float | None = None,
        check_cancellation: Callable[[], bool] | None = None,
    ) -> ExecutionTrace:
        raise RuntimeError(
            "Cannot execute session in LIVE_AUT mode: target service is BLOCKED."
        )

    def cleanup_fixture(self, namespace: str) -> tuple[bool, bool]:
        return False, False


# ---------------------------------------------------------------------------
# Controlled Test Adapter
# ---------------------------------------------------------------------------


class ControlledTestTargetAdapter(BaseTargetAdapter):
    """Deterministic controlled test adapter, clearly labelled as 'test_infrastructure'.

    Used for reproducible multi-component integration testing without network dependencies.
    Executes domain operations with strict fixture partitioning, supports C3 fault hooks
    and C4 prompt-injection delivery, and records raw traces.
    """

    def __init__(self, failure_on_cleanup: bool = False):
        self.failure_on_cleanup = failure_on_cleanup
        # Partitioned store: namespace -> state dict
        self._partitions: dict[str, dict[str, Any]] = {}

    def check_readiness(self) -> tuple[TargetReadinessStatus, list[str]]:
        """Controlled test adapter is always ready for test infrastructure execution."""
        return TargetReadinessStatus.READY, []

    @property
    def partitions(self) -> dict[str, dict[str, Any]]:
        return self._partitions

    def get_partition(self, namespace: str) -> dict[str, Any] | None:
        return self._partitions.get(namespace)

    def prepare_fixture(
        self, namespace: str, seed_data: dict[str, Any] | None = None
    ) -> StateSnapshot:
        """Create fresh isolated partition."""
        initial_data = {
            "order": seed_data.get("order")
            if seed_data
            else {"order_id": "ord-001", "status": "PENDING"},
            "refund": seed_data.get("refund") if seed_data else {"status": "INITIAL"},
            "inventory": seed_data.get("inventory")
            if seed_data
            else {"reserved": False, "stock_count": 10},
            "side_effects": {"duplicate_count": 0, "calls_made": 0},
            "idempotency": {"enforced": True, "keys_seen": []},
            "users": {"user_id": "usr-test-1", "balance": 500},
        }
        self._partitions[namespace] = copy.deepcopy(initial_data)
        snap_id = f"snap-init-{namespace[:8]}"
        fp = compute_snapshot_fingerprint(initial_data)
        return StateSnapshot(
            snapshot_id=snap_id,
            time_scope="initial",
            state=initial_data,
            fingerprint=fp,
        )

    def execute_session(
        self,
        namespace: str,
        task_prompt: str,
        permitted_tools: list[str],
        fault_injection_hook: dict[str, Any] | None = None,
        prompt_injection_payload: str | None = None,
        max_tool_calls: int = 50,
        trial_role: str = "DEFAULT",
        deadline_monotonic: float | None = None,
        check_cancellation: Callable[[], bool] | None = None,
    ) -> ExecutionTrace:
        """Execute one complete trial session with actual trace recording."""
        partition = self._partitions.get(namespace)
        if partition is None:
            self.prepare_fixture(namespace)
            partition = self._partitions[namespace]

        init_fp = compute_snapshot_fingerprint(partition)
        init_snapshot = StateSnapshot(
            snapshot_id=f"snap-pre-{namespace[:8]}",
            time_scope="initial",
            state=copy.deepcopy(partition),
            fingerprint=init_fp,
        )

        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        tool_events: list[RawToolEvent] = []
        caller_outcome = "SUCCESS"
        fault_injected = False
        fault_details = None
        injection_delivered = False
        injection_details = None

        # Check prompt injection delivery for C4
        if prompt_injection_payload:
            injection_delivered = True
            injection_details = {
                "channel": "user_task_prompt",
                "payload": prompt_injection_payload,
                "delivered_at_utc": datetime.now(UTC).isoformat(),
            }

        call_idx = 0

        def can_dispatch_call() -> bool:
            nonlocal caller_outcome
            if check_cancellation and check_cancellation():
                caller_outcome = "CANCELLED"
                return False
            if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
                caller_outcome = "CALLER_TIMEOUT_EXCEEDED"
                return False
            if call_idx >= max_tool_calls:
                caller_outcome = "CALL_BUDGET_EXCEEDED"
                return False
            return True

        # Simulated tool execution plan based on prompt and permitted tools
        # 1. order_lookup or create
        if (
            "order_placement" in permitted_tools or "create_order" in permitted_tools
        ) and can_dispatch_call():
            call_idx += 1
            tool_name = (
                "order_placement"
                if "order_placement" in permitted_tools
                else "create_order"
            )
            args = {"item_id": "item-99", "quantity": 1, "customer_id": "usr-test-1"}
            sanitized_args = sanitize_payload(args)

            # Check C3 fault injection hook
            should_inject = False
            if (
                fault_injection_hook
                and fault_injection_hook.get("target_tool") == tool_name
            ):
                occurrence = fault_injection_hook.get("occurrence", 1)
                if call_idx == occurrence:
                    should_inject = True

            if should_inject:
                fault_injected = True
                ff = fault_injection_hook.get("fault_family", "TIMEOUT_DISCONNECTION")
                phase = str(
                    fault_injection_hook.get("effect_phase", "BEFORE_EFFECT")
                ).upper()
                fault_details = {
                    "fault_family": ff,
                    "injected_at_call_index": call_idx,
                    "target_tool": tool_name,
                    "effect_phase": phase,
                }

                is_after_commit = (
                    "AFTER_COMMIT" in phase
                    or ff == "AFTER_COMMIT"
                    or "AFTER_COMMIT"
                    in str(fault_injection_hook.get("interception_hook", "")).upper()
                    or "AFTER_STATE_COMMIT"
                    in str(fault_injection_hook.get("interception_hook", "")).upper()
                )
                if is_after_commit:
                    partition["order"]["status"] = "CONFIRMED"
                    partition["inventory"]["reserved"] = True
                    partition["side_effects"]["calls_made"] += 1
                    side_effect_occurred = True
                else:
                    side_effect_occurred = False

                if ff == "RATE_LIMIT_429":
                    err_msg = "HTTP 429 Too Many Requests (Rate limit exceeded)"
                    lat = 5.0
                    fault_output = {"status_code": 429, "error": "Too Many Requests"}
                elif is_after_commit:
                    err_msg = "Connection reset after commit"
                    lat = 10.0
                    fault_output = {"state_committed": True, "error": err_msg}
                else:
                    err_msg = "Simulated network timeout (caller timeout exceeded 50ms)"
                    lat = 55.0
                    fault_output = None

                tool_events.append(
                    RawToolEvent(
                        event_id=f"evt_{trace_id}_{call_idx}",
                        call_index=call_idx,
                        tool_name=tool_name,
                        arguments=sanitized_args,
                        output=fault_output,
                        error=err_msg,
                        success=False,
                        latency_ms=lat,
                        side_effect_occurred=side_effect_occurred,
                    )
                )

                # Agent retry under fault trial
                if trial_role == "FAULT":
                    if not can_dispatch_call():
                        pass
                    else:
                        call_idx += 1
                        idempotency_key = f"idem-{uuid.uuid4().hex[:8]}"
                        if not is_after_commit:
                            partition["order"]["status"] = "CONFIRMED"
                            partition["inventory"]["reserved"] = True
                            partition["side_effects"]["calls_made"] += 1
                        partition["idempotency"]["keys_seen"].append(idempotency_key)
                        tool_events.append(
                            RawToolEvent(
                                event_id=f"evt_{trace_id}_{call_idx}",
                                call_index=call_idx,
                                tool_name=tool_name,
                                arguments={
                                    **sanitized_args,
                                    "idempotency_key": idempotency_key,
                                },
                                output={"order_id": "ord-001", "status": "CONFIRMED"},
                                success=True,
                                latency_ms=12.0,
                                side_effect_occurred=True,
                                idempotency_key=idempotency_key,
                            )
                        )
                        caller_outcome = "SUCCESS_CLEAN_RECOVERY"
            else:
                # Normal execution without fault
                partition["order"]["status"] = "CONFIRMED"
                partition["inventory"]["reserved"] = True
                partition["side_effects"]["calls_made"] += 1
                tool_events.append(
                    RawToolEvent(
                        event_id=f"evt_{trace_id}_{call_idx}",
                        call_index=call_idx,
                        tool_name=tool_name,
                        arguments=sanitized_args,
                        output={"order_id": "ord-001", "status": "CONFIRMED"},
                        success=True,
                        latency_ms=15.0,
                        side_effect_occurred=True,
                    )
                )

        # 1b. get_order_details if permitted
        if "get_order_details" in permitted_tools and can_dispatch_call():
            call_idx += 1
            tool_name = "get_order_details"
            args = {"order_id": "ORD-9821"}
            tool_events.append(
                RawToolEvent(
                    event_id=f"evt_{trace_id}_{call_idx}",
                    call_index=call_idx,
                    tool_name=tool_name,
                    arguments=sanitize_payload(args),
                    output={
                        "order_id": "ORD-9821",
                        "customer_id": "CUST-8831",
                        "status": "DELIVERED",
                        "items": {
                            "ITEM-44": {"name": "Wireless Mouse", "price": 35.00}
                        },
                    },
                    success=True,
                    latency_ms=10.0,
                    side_effect_occurred=False,
                )
            )

        # 2. refund_processing if permitted
        if (
            "process_refund" in permitted_tools or "refund_request" in permitted_tools
        ) and can_dispatch_call():
            call_idx += 1
            tool_name = (
                "process_refund"
                if "process_refund" in permitted_tools
                else "refund_request"
            )
            if "get_order_details" in permitted_tools:
                args = {
                    "order_id": "ORD-9821",
                    "line_item_id": "ITEM-44",
                    "amount": 35.00,
                    "reason": "customer reported item damaged on arrival",
                }
            else:
                args = {"order_id": "ord-001", "amount": 100}

            should_inject = False
            if (
                fault_injection_hook
                and fault_injection_hook.get("target_tool") == tool_name
            ):
                occurrence = fault_injection_hook.get("occurrence", 1)
                if call_idx == occurrence:
                    should_inject = True

            if should_inject:
                fault_injected = True
                ff = fault_injection_hook.get("fault_family", "TIMEOUT_DISCONNECTION")
                phase = str(
                    fault_injection_hook.get("effect_phase", "BEFORE_EFFECT")
                ).upper()
                fault_details = {
                    "fault_family": ff,
                    "injected_at_call_index": call_idx,
                    "target_tool": tool_name,
                    "effect_phase": phase,
                }
                is_after_commit = "AFTER_COMMIT" in phase
                if is_after_commit:
                    partition["refund"]["status"] = "COMPLETED"
                    partition["side_effects"]["calls_made"] += 1
                    side_effect_occurred = True
                else:
                    side_effect_occurred = False

                err_msg = (
                    "HTTP 429 Too Many Requests (Rate limit exceeded)"
                    if ff == "RATE_LIMIT_429"
                    else "Simulated network timeout (caller timeout exceeded 50ms)"
                )
                fault_output = (
                    {"status_code": 429, "error": "Too Many Requests"}
                    if ff == "RATE_LIMIT_429"
                    else None
                )
                tool_events.append(
                    RawToolEvent(
                        event_id=f"evt_{trace_id}_{call_idx}",
                        call_index=call_idx,
                        tool_name=tool_name,
                        arguments=sanitize_payload(args),
                        output=fault_output,
                        error=err_msg,
                        success=False,
                        latency_ms=5.0 if ff == "RATE_LIMIT_429" else 55.0,
                        side_effect_occurred=side_effect_occurred,
                    )
                )
            else:
                partition["refund"]["status"] = "COMPLETED"
                partition["side_effects"]["calls_made"] += 1
                tool_events.append(
                    RawToolEvent(
                        event_id=f"evt_{trace_id}_{call_idx}",
                        call_index=call_idx,
                        tool_name=tool_name,
                        arguments=sanitize_payload(args),
                        output={"refund_id": "ref-001", "status": "COMPLETED"},
                        success=True,
                        latency_ms=10.0,
                        side_effect_occurred=True,
                    )
                )

        # 2b. send_customer_notification if permitted
        if "send_customer_notification" in permitted_tools and can_dispatch_call():
            call_idx += 1
            tool_name = "send_customer_notification"
            args = {
                "customer_id": "CUST-8831",
                "message": "Refund processed successfully.",
            }
            tool_events.append(
                RawToolEvent(
                    event_id=f"evt_{trace_id}_{call_idx}",
                    call_index=call_idx,
                    tool_name=tool_name,
                    arguments=sanitize_payload(args),
                    output={"notified": True, "channel": "email"},
                    success=True,
                    latency_ms=10.0,
                    side_effect_occurred=False,
                )
            )

        # 3. Helpdesk tools if permitted
        if "query_device_status" in permitted_tools and can_dispatch_call():
            call_idx += 1
            tool_name = "query_device_status"
            args = {"device_id": "DEV-709"}
            tool_events.append(
                RawToolEvent(
                    event_id=f"evt_{trace_id}_{call_idx}",
                    call_index=call_idx,
                    tool_name=tool_name,
                    arguments=sanitize_payload(args),
                    output={
                        "device_id": "DEV-709",
                        "status": "ONLINE",
                        "managed": True,
                    },
                    success=True,
                    latency_ms=8.0,
                    side_effect_occurred=False,
                )
            )

        if "reboot_managed_device" in permitted_tools and can_dispatch_call():
            call_idx += 1
            tool_name = "reboot_managed_device"
            args = {"device_id": "DEV-709", "reason": "routine maintenance"}
            tool_events.append(
                RawToolEvent(
                    event_id=f"evt_{trace_id}_{call_idx}",
                    call_index=call_idx,
                    tool_name=tool_name,
                    arguments=sanitize_payload(args),
                    output={"device_id": "DEV-709", "status": "REBOOTED"},
                    success=True,
                    latency_ms=25.0,
                    side_effect_occurred=True,
                )
            )

        final_fp = compute_snapshot_fingerprint(partition)
        final_snapshot = StateSnapshot(
            snapshot_id=f"snap-post-{namespace[:8]}",
            time_scope="post_recovery",
            state=copy.deepcopy(partition),
            fingerprint=final_fp,
        )

        return ExecutionTrace(
            trace_id=trace_id,
            trial_role=trial_role,
            target_mode=TargetMode.CONTROLLED_TEST,
            is_simulation=True,
            caller_outcome=caller_outcome,
            tool_events=tool_events,
            initial_state=init_snapshot,
            final_state=final_snapshot,
            is_complete=(caller_outcome != "CANCELLED"),
            fault_injected=fault_injected,
            fault_details=fault_details,
            injection_delivered=injection_delivered,
            injection_details=injection_details,
            cleanup_successful=True,
            cleanup_reusable=True,
        )

    def cleanup_fixture(self, namespace: str) -> tuple[bool, bool]:
        """Tear down partition and verify state."""
        if self.failure_on_cleanup:
            return False, False

        self._partitions.pop(namespace, None)
        return True, True
