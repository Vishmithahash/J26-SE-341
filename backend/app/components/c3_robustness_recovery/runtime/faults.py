"""Supported fault delivery mechanisms for Component 3 operational fault families.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.components.c3_robustness_recovery.contracts.schemas import (
    FaultFamily,
    MalformedResponseMode,
)
from app.components.c3_robustness_recovery.runtime.adapter import ToolExecutionResult


@dataclass(frozen=True)
class FaultDeliveryResult:
    """Outcome of delivering a simulated operational fault to a caller."""

    result: ToolExecutionResult | None = None
    raised_exception: Exception | None = None
    status_code: int | None = None
    retry_after_seconds: int | None = None
    unavailability_mode: str | None = None
    malformed_fragment: str | None = None


class FaultDeliveryHandler(ABC):
    """Abstract strategy for simulating an operational fault delivery at the domain tool boundary."""

    @abstractmethod
    async def deliver_fault(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        plan: Any,
        context: dict[str, Any] | None = None,
    ) -> FaultDeliveryResult:
        """Deliver the simulated fault condition to the caller."""


class Transient5xxDeliveryHandler(FaultDeliveryHandler):
    """Delivers transient HTTP 5xx server errors without forwarding on BEFORE_EFFECT."""

    async def deliver_fault(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        plan: Any,
        context: dict[str, Any] | None = None,
    ) -> FaultDeliveryResult:
        payload = getattr(plan, "payload_details", {})
        mode_val = (
            getattr(plan, "fault_mode", "")
            if isinstance(getattr(plan, "fault_mode", ""), str)
            else getattr(getattr(plan, "fault_mode", ""), "value", "HTTP_500")
        )
        status_map = {
            "HTTP_500": 500,
            "HTTP_502": 502,
            "HTTP_503": 503,
            "HTTP_504": 504,
        }
        status_code = status_map.get(mode_val, int(payload.get("http_status", 500)))
        error_msg = payload.get(
            "error_message", f"Simulated server-side {status_code} response."
        )

        res = ToolExecutionResult(
            success=False,
            tool_id=tool_id,
            tool_version=tool_version,
            error=f"HTTP {status_code}: {error_msg}",
            output={
                "http_status": status_code,
                "message": error_msg,
                "transient": True,
            },
            latency_ms=2.0,
            side_effect_occurred=False,
        )
        return FaultDeliveryResult(
            result=res,
            status_code=status_code,
        )


class RateLimit429DeliveryHandler(FaultDeliveryHandler):
    """Delivers HTTP 429 Too Many Requests response with explicit Retry-After header semantics."""

    async def deliver_fault(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        plan: Any,
        context: dict[str, Any] | None = None,
    ) -> FaultDeliveryResult:
        payload = getattr(plan, "payload_details", {})
        retry_after = payload.get("retry_after_seconds")
        # retry_after may be None (absent), 0, or positive integer
        headers: dict[str, Any] = {"Status": "429 Too Many Requests"}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        res = ToolExecutionResult(
            success=False,
            tool_id=tool_id,
            tool_version=tool_version,
            error=f"HTTP 429: Rate limit exceeded (Retry-After: {retry_after}).",
            output={
                "http_status": 429,
                "headers": headers,
                "retry_after_seconds": retry_after,
            },
            latency_ms=1.5,
            side_effect_occurred=False,
        )
        return FaultDeliveryResult(
            result=res,
            status_code=429,
            retry_after_seconds=retry_after,
        )


class ToolUnavailabilityDeliveryHandler(FaultDeliveryHandler):
    """Delivers tool unavailability (circuit broken, maintenance window, dependency offline)."""

    async def deliver_fault(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        plan: Any,
        context: dict[str, Any] | None = None,
    ) -> FaultDeliveryResult:
        payload = getattr(plan, "payload_details", {})
        mode_val = (
            getattr(plan, "fault_mode", "")
            if isinstance(getattr(plan, "fault_mode", ""), str)
            else getattr(getattr(plan, "fault_mode", ""), "value", "CIRCUIT_BROKEN")
        )
        retryable = bool(payload.get("retryable", False))

        res = ToolExecutionResult(
            success=False,
            tool_id=tool_id,
            tool_version=tool_version,
            error=f"Tool unavailable: {mode_val} (retryable={retryable}).",
            output={
                "unavailability_mode": mode_val,
                "retryable": retryable,
                "status": "UNAVAILABLE",
            },
            latency_ms=2.0,
            side_effect_occurred=False,
        )
        return FaultDeliveryResult(
            result=res,
            unavailability_mode=mode_val,
        )


class MalformedResponseDeliveryHandler(FaultDeliveryHandler):
    """Delivers malformed response content at the consumption boundary."""

    async def deliver_fault(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        plan: Any,
        context: dict[str, Any] | None = None,
    ) -> FaultDeliveryResult:
        mode_val = (
            getattr(plan, "fault_mode", "")
            if isinstance(getattr(plan, "fault_mode", ""), str)
            else getattr(getattr(plan, "fault_mode", ""), "value", "INVALID_JSON")
        )

        if mode_val == MalformedResponseMode.INVALID_JSON.value:
            raw_payload = '{"order_id": 123, <<malformed_syntax>>'
            exc = json.JSONDecodeError(
                "Expecting property name enclosed in double quotes", raw_payload, 18
            )
            return FaultDeliveryResult(
                raised_exception=exc,
                malformed_fragment=raw_payload,
            )

        if mode_val == MalformedResponseMode.TRUNCATED_JSON.value:
            raw_payload = '{"order_id": "ord-demo-trunc", "status":'
            exc = json.JSONDecodeError(
                "Unexpected end of input in JSON content", raw_payload, len(raw_payload)
            )
            return FaultDeliveryResult(
                raised_exception=exc,
                malformed_fragment=raw_payload,
            )

        if mode_val == MalformedResponseMode.SCHEMA_VIOLATION.value:
            raw_payload = '{"unexpected_root_field": 42, "malformed": true}'
            res = ToolExecutionResult(
                success=False,
                tool_id=tool_id,
                tool_version=tool_version,
                error="SchemaValidationError: Response body does not match expected tool output schema",
                output={"raw_content": raw_payload, "malformed_mode": mode_val},
                latency_ms=1.0,
                side_effect_occurred=False,
            )
            return FaultDeliveryResult(
                result=res,
                malformed_fragment=raw_payload,
            )

        # EMPTY_BODY
        raw_payload = "<empty_body>"
        exc = json.JSONDecodeError("Empty body received: expected JSON document", "", 0)
        return FaultDeliveryResult(
            raised_exception=exc,
            malformed_fragment=raw_payload,
        )


def get_fault_handler(family: FaultFamily) -> FaultDeliveryHandler:
    """Return the concrete delivery handler for the declared fault family."""
    if family == FaultFamily.TRANSIENT_5XX:
        return Transient5xxDeliveryHandler()
    if family == FaultFamily.RATE_LIMIT_429:
        return RateLimit429DeliveryHandler()
    if family == FaultFamily.TOOL_UNAVAILABILITY:
        return ToolUnavailabilityDeliveryHandler()
    if family == FaultFamily.MALFORMED_RESPONSE:
        return MalformedResponseDeliveryHandler()
    raise ValueError(
        f"No delivery handler registered for fault family '{family.value}'."
    )
