"""Independent state observer for C2 workflow evaluation.

Captures application state snapshots before and after each observable action,
calculates explicit state differences, redacts secrets, and preserves missing
observations separately from explicit nulls.
Does NOT construct state by applying oracle expectations or copying reference paths.
"""

import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvent,
    StateObservation,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT

SENSITIVE_FIELD_NAMES = {
    "password",
    "secret",
    "token",
    "auth",
    "authorization",
    "api_key",
    "apikey",
    "credit_card",
    "cvv",
}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive key values while preserving data structure."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in str(k).lower() for s in SENSITIVE_FIELD_NAMES):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    if isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


def compute_state_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compute explicit differences between before and after state snapshots."""
    diff: dict[str, Any] = {}
    all_keys = set(before.keys()) | set(after.keys())
    for k in sorted(all_keys):
        if k not in before:
            diff[k] = {"before": None, "after": after[k], "action": "ADDED"}
        elif k not in after:
            diff[k] = {"before": before[k], "after": None, "action": "REMOVED"}
        elif before[k] != after[k]:
            diff[k] = {"before": before[k], "after": after[k], "action": "MODIFIED"}
    return diff


class IndependentStateObserver:
    """Observes tool executions on an independent SUT.

    Captures state immediately before and after the action, logs the observed
    event, and calculates state diffs without knowing reference paths or expected answers.
    """

    def __init__(self, sut: SyntheticRefundSUT):
        self.sut = sut
        self.events: list[RuntimeEvent] = []
        self.observations: list[StateObservation] = []

    def observe_tool_call(
        self,
        event_index: int,
        event_id: str,
        tool_name: str,
        tool_callable: Callable[..., Any],
        arguments: dict[str, Any],
        tool_call_correlation_id: str | None = None,
        entity_identifiers: dict[str, Any] | None = None,
    ) -> Any:
        """Execute tool on SUT with pre- and post-state observation."""
        # 1. Capture snapshot before execution
        raw_before = self.sut.get_state_snapshot()
        before_state = redact_sensitive_data(raw_before)

        # 2. Execute actual tool action
        error_msg: str | None = None
        observable_result: Any = None
        try:
            observable_result = tool_callable(**arguments)
            if (
                isinstance(observable_result, dict)
                and observable_result.get("status") == "ERROR"
            ):
                error_msg = observable_result.get("error")
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            observable_result = {"status": "EXCEPTION", "error": error_msg}

        # 3. Capture snapshot after execution
        raw_after = self.sut.get_state_snapshot()
        after_state = redact_sensitive_data(raw_after)

        # 4. Calculate state diff
        state_diff = compute_state_diff(before_state, after_state)

        # 5. Extract entity identifiers if not explicitly provided
        entities = dict(entity_identifiers or {})
        for k in ("customer_id", "order_id", "refund_id"):
            if k in arguments and k not in entities:
                entities[k] = arguments[k]
            elif (
                isinstance(observable_result, dict)
                and k in observable_result
                and k not in entities
            ):
                entities[k] = observable_result[k]

        event = RuntimeEvent(
            event_index=event_index,
            event_id=event_id,
            tool_call_correlation_id=tool_call_correlation_id or f"corr_{event_id}",
            timestamp=datetime.now(UTC),
            tool_name=tool_name,
            arguments=redact_sensitive_data(copy.deepcopy(arguments)),
            observable_result=redact_sensitive_data(copy.deepcopy(observable_result)),
            error=error_msg,
            entity_identifiers=entities,
        )

        observation = StateObservation(
            event_index=event_index,
            before_state=before_state,
            after_state=after_state,
            state_diff=state_diff,
        )

        self.events.append(event)
        self.observations.append(observation)

        return observable_result
