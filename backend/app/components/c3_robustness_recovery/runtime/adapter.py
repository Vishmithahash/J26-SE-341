"""Domain tool and fixture interfaces, demonstration implementations, and live readiness checks.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 2 - One-tool integration, matched trials, verified timeout exposure and safeguards.
"""

import copy
import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CapabilityCombination,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    OccurrenceBounds,
    ReleaseRuleType,
    ToolCapabilityDeclaration,
    ToolMutability,
)


class TargetMode(str, Enum):
    """Execution target mode: generic demonstration or live AUT."""

    DEMONSTRATION = "DEMONSTRATION"
    LIVE_AUT = "LIVE_AUT"


class CallerIdentity(str, Enum):
    """Caller executing the test task."""

    SCRIPTED_CALLER = "SCRIPTED_CALLER"
    ACTUAL_AGENT = "ACTUAL_AGENT"


class RecoveryActor(str, Enum):
    """Entity that made the retry or fallback decision."""

    AGENT = "AGENT"
    SDK = "SDK"
    ADAPTER = "ADAPTER"
    MIDDLEWARE = "MIDDLEWARE"
    SCRIPTED_CALLER = "SCRIPTED_CALLER"
    UNKNOWN = "UNKNOWN"


class CleanupStatus(str, Enum):
    """Status of fixture cleanup after trial execution."""

    CLEANED_AND_VERIFIED = "CLEANED_AND_VERIFIED"
    UNCERTAIN = "UNCERTAIN"
    FAILED = "FAILED"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class CleanupResult:
    """Outcome of fixture cleanup and verification."""

    status: CleanupStatus
    details: str
    reusable: bool
    in_flight_count: int = 0
    final_fingerprint: str | None = None


@dataclass
class ToolExecutionResult:
    """Standardized result of a domain tool invocation."""

    success: bool
    tool_id: str
    tool_version: str
    output: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    side_effect_occurred: bool = False
    idempotency_key: str | None = None


class DomainToolAdapter(ABC):
    """Abstract base contract for a domain tool adapter."""

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Declared identifier for the adapter."""

    @property
    @abstractmethod
    def adapter_version(self) -> str:
        """Declared semantic version for the adapter."""

    @property
    @abstractmethod
    def target_mode(self) -> TargetMode:
        """Target execution mode."""

    @abstractmethod
    def get_manifest(self) -> AdapterCapabilityManifest:
        """Return the capability manifest for this adapter."""

    @abstractmethod
    async def execute_tool(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        call_context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Execute the tool against the target (demonstration or live)."""


class FixtureManager(ABC):
    """Abstract base contract for fixture isolation, reset, observation, and cleanup."""

    @property
    @abstractmethod
    def fixture_id(self) -> str:
        """Declared fixture identifier."""

    @property
    @abstractmethod
    def fixture_version(self) -> str:
        """Declared fixture version."""

    @abstractmethod
    def prepare_fixture(
        self, namespace: str, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Prepare and isolate a fixture namespace before a trial."""

    @abstractmethod
    def reset_fixture(self, namespace: str) -> None:
        """Reset the given fixture namespace to baseline."""

    @abstractmethod
    def observe_state(self, namespace: str) -> dict[str, Any]:
        """Independently observe state for the specified namespace."""

    @abstractmethod
    def compute_state_fingerprint(self, state: dict[str, Any]) -> str:
        """Compute a deterministic hash fingerprint of the logical state."""

    @abstractmethod
    def cleanup(self, namespace: str) -> CleanupResult:
        """Safely clean up and verify no pending operations or leaked state."""


# ---------------------------------------------------------------------------
# Demonstration Implementations
# ---------------------------------------------------------------------------


class DemonstrationFixtureManager(FixtureManager):
    """Demonstration fixture manager maintaining isolated namespace state stores.

    Each trial receives a strictly separated namespace to prevent cross-trial contamination.
    """

    def __init__(
        self,
        fixture_id: str = "fix-demonstration-cart",
        fixture_version: str = "1.0.0",
    ) -> None:
        self._fixture_id = fixture_id
        self._fixture_version = fixture_version
        self._namespaces: dict[str, dict[str, Any]] = {}
        self._in_flight: dict[str, int] = {}
        self._unclean_namespaces: set[str] = set()

    @property
    def fixture_id(self) -> str:
        return self._fixture_id

    @property
    def fixture_version(self) -> str:
        return self._fixture_version

    def prepare_fixture(
        self, namespace: str, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if namespace in self._unclean_namespaces:
            raise RuntimeError(
                f"Namespace '{namespace}' is marked UNCLEAN and cannot be reused."
            )
        initial_balance = config.get("initial_balance", 500) if config else 500
        initial_items = (
            copy.deepcopy(config.get("cart_items", []))
            if config
            else [
                {
                    "item_id": "item-demo-001",
                    "name": "Mechanical Keyboard",
                    "quantity": 1,
                    "unit_price": 100,
                }
            ]
        )
        self._namespaces[namespace] = {
            "customer_id": "cust-demo-100",
            "balance": initial_balance,
            "cart_items": initial_items,
            "orders": [],
            "order_count": 0,
        }
        self._in_flight[namespace] = 0
        return self.observe_state(namespace)

    def reset_fixture(self, namespace: str) -> None:
        if namespace in self._namespaces:
            self._namespaces[namespace]["orders"] = []
            self._namespaces[namespace]["order_count"] = 0
            self._namespaces[namespace]["balance"] = 500
            self._in_flight[namespace] = 0

    def observe_state(self, namespace: str) -> dict[str, Any]:
        if namespace not in self._namespaces:
            return {}
        # Return a deep copy of logical state (excluding internal physical counters)
        raw = self._namespaces[namespace]
        return {
            "customer_id": raw["customer_id"],
            "balance": raw["balance"],
            "cart_items": copy.deepcopy(raw["cart_items"]),
            "orders": copy.deepcopy(raw["orders"]),
            "order_count": raw["order_count"],
        }

    def compute_state_fingerprint(self, state: dict[str, Any]) -> str:
        """Compute SHA256 hex digest of sorted canonical JSON representation."""
        canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def record_in_flight_start(self, namespace: str) -> None:
        self._in_flight[namespace] = self._in_flight.get(namespace, 0) + 1

    def record_in_flight_end(self, namespace: str) -> None:
        self._in_flight[namespace] = max(0, self._in_flight.get(namespace, 1) - 1)

    def cleanup(self, namespace: str) -> CleanupResult:
        in_flight = self._in_flight.get(namespace, 0)
        if in_flight > 0:
            self._unclean_namespaces.add(namespace)
            return CleanupResult(
                status=CleanupStatus.UNCERTAIN,
                details=f"Cleanup uncertain: {in_flight} operations were still in-flight at cleanup time.",
                reusable=False,
                in_flight_count=in_flight,
            )

        if namespace not in self._namespaces:
            return CleanupResult(
                status=CleanupStatus.CLEANED_AND_VERIFIED,
                details=f"Namespace '{namespace}' already cleared or not initialized.",
                reusable=True,
                in_flight_count=0,
            )

        # Settle state and verify final observation
        final_state = self.observe_state(namespace)
        final_fp = self.compute_state_fingerprint(final_state)

        # Drop memory references for isolation
        del self._namespaces[namespace]
        if namespace in self._in_flight:
            del self._in_flight[namespace]

        return CleanupResult(
            status=CleanupStatus.CLEANED_AND_VERIFIED,
            details=f"Namespace '{namespace}' successfully settled, observed, and removed.",
            reusable=True,
            in_flight_count=0,
            final_fingerprint=final_fp,
        )

    def verify_committed_operation(self, namespace: str, operation_id: str) -> bool:
        """Independent observation facility to confirm whether an operation committed."""
        store = self._namespaces.get(namespace)
        if not store:
            return False
        for order in store.get("orders", []):
            if (
                order.get("order_id") == operation_id
                and order.get("status") == "CONFIRMED"
            ):
                return True
        return False


class DemonstrationToolAdapter(DomainToolAdapter):
    """Generic demonstration adapter for Phase 2 and Phase 3 local hermetic testing.

    Provides ONE side-effecting domain tool: demonstration_order_placement.
    Target mode is strictly DEMONSTRATION.
    """

    def __init__(
        self,
        fixture_manager: DemonstrationFixtureManager,
        adapter_id: str = "adapter-demonstration-c3",
        adapter_version: str = "1.0.0",
    ) -> None:
        self._fixture_manager = fixture_manager
        self._adapter_id = adapter_id
        self._adapter_version = adapter_version

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def adapter_version(self) -> str:
        return self._adapter_version

    @property
    def target_mode(self) -> TargetMode:
        return TargetMode.DEMONSTRATION

    def get_manifest(self) -> AdapterCapabilityManifest:
        return AdapterCapabilityManifest(
            adapter_id=self._adapter_id,
            adapter_version=self._adapter_version,
            schema_version="1.0.0",
            tools=[
                ToolCapabilityDeclaration(
                    tool_id="demonstration_order_placement",
                    tool_version="1.0.0",
                    mutability=ToolMutability.SIDE_EFFECTING,
                )
            ],
            supported_combinations=[
                # 1. TIMEOUT_DISCONNECTION (BEFORE_EFFECT)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "CALLER_TIMEOUT_EXCEEDED",
                        "HANG_INDEFINITELY",
                    ],
                    required_observation_capabilities=["caller_timeout_observed"],
                ),
                # 2. TIMEOUT_DISCONNECTION (AFTER_COMMIT lost-response)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                    effect_phase=EffectPhase.AFTER_COMMIT,
                    interception_hook=InterceptionHook.APPLICATION_AWARE_HOOK,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "CALLER_TIMEOUT_EXCEEDED",
                    ],
                    required_observation_capabilities=["committed_order_verified"],
                ),
                # 3. TRANSIENT_5XX (BEFORE_EFFECT)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.TRANSIENT_5XX,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "HTTP_500",
                        "HTTP_502",
                        "HTTP_503",
                        "HTTP_504",
                    ],
                    required_observation_capabilities=["transient_5xx_observed"],
                ),
                # 4. RATE_LIMIT_429 (BEFORE_EFFECT)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.RATE_LIMIT_429,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "RATE_LIMIT_EXCEEDED",
                    ],
                    required_observation_capabilities=["rate_limit_observed"],
                ),
                # 5. TOOL_UNAVAILABILITY (BEFORE_EFFECT)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.TOOL_UNAVAILABILITY,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "CIRCUIT_BROKEN",
                        "SERVICE_MAINTENANCE",
                        "DEPENDENCY_OFFLINE",
                        "RESOURCE_EXHAUSTED",
                    ],
                    required_observation_capabilities=["unavailability_observed"],
                ),
                # 6. MALFORMED_RESPONSE (BEFORE_EFFECT)
                CapabilityCombination(
                    tool_id="demonstration_order_placement",
                    fault_family=FaultFamily.MALFORMED_RESPONSE,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=1
                    ),
                    allowed_release_rule_types=[
                        ReleaseRuleType.ATTEMPT_BOUNDED,
                        ReleaseRuleType.IMMEDIATE,
                    ],
                    supported_payload_modes=[
                        "INVALID_JSON",
                        "TRUNCATED_JSON",
                        "SCHEMA_VIOLATION",
                        "EMPTY_BODY",
                    ],
                    required_observation_capabilities=["malformed_response_observed"],
                ),
            ],
        )

    async def execute_tool(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        call_context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        start_time = time.perf_counter()
        if tool_id != "demonstration_order_placement":
            return ToolExecutionResult(
                success=False,
                tool_id=tool_id,
                tool_version=tool_version,
                error=f"Tool '{tool_id}' is not supported by DemonstrationToolAdapter.",
                latency_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        namespace = (call_context or {}).get("namespace", "default")
        self._fixture_manager.record_in_flight_start(namespace)
        try:
            # Validate and apply domain side effect
            item_id = arguments.get("item_id", "item-demo-001")
            quantity = int(arguments.get("quantity", 1))
            unit_price = int(arguments.get("unit_price", 100))
            total_amount = quantity * unit_price
            order_id = (
                arguments.get("order_id") or f"ord-demo-{int(time.time() * 1000)}"
            )

            store = self._fixture_manager._namespaces.get(namespace)
            if not store:
                return ToolExecutionResult(
                    success=False,
                    tool_id=tool_id,
                    tool_version=tool_version,
                    error=f"Namespace '{namespace}' not found in fixture manager.",
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                )

            if store["balance"] < total_amount:
                return ToolExecutionResult(
                    success=False,
                    tool_id=tool_id,
                    tool_version=tool_version,
                    error="Insufficient balance for order.",
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                )

            # Apply state mutation
            store["balance"] -= total_amount
            order_record = {
                "order_id": order_id,
                "item_id": item_id,
                "quantity": quantity,
                "total_amount": total_amount,
                "status": "CONFIRMED",
            }
            store["orders"].append(order_record)
            store["order_count"] += 1

            latency = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResult(
                success=True,
                tool_id=tool_id,
                tool_version=tool_version,
                output={
                    "order_id": order_id,
                    "status": "CONFIRMED",
                    "charged_amount": total_amount,
                    "remaining_balance": store["balance"],
                },
                latency_ms=latency,
                side_effect_occurred=True,
                idempotency_key=arguments.get("idempotency_key"),
            )
        finally:
            self._fixture_manager.record_in_flight_end(namespace)


# ---------------------------------------------------------------------------
# Real Target Integration Blocker Check & Connector Contract
# ---------------------------------------------------------------------------

FUTURE_NEXACART_REQUIRED_CAPABILITIES: list[str] = [
    "Agent invocation and failed-run trace retrieval",
    "Domain tool-call interception",
    "Fixture preparation and reset facilities",
    "Independent state observations",
    "Operation completion and settling evidence",
    "Correlated event, trial, and operation identifiers",
]


def check_real_target_prerequisites(
    adapter_id: str | None = None,
) -> tuple[bool, list[str]]:
    """Check whether real target (e.g. NexaCart AUT) prerequisites are available.

    Safeguard: A configured URL, health check, or env var alone must NOT mark live
    execution ready. The live NexaCart connector must implement and register all 6
    required domain adapter and fixture capabilities.
    """
    missing: list[str] = []

    # Check for target endpoint
    target_url = os.environ.get("NEXACART_AUT_URL") or os.environ.get("AUT_TARGET_URL")
    if not target_url:
        missing.append(
            "Target Application-Under-Test endpoint is not configured (set NEXACART_AUT_URL or AUT_TARGET_URL)."
        )

    # Check for verified OpenAPI specification
    openapi_path = os.environ.get("NEXACART_OPENAPI_SPEC") or os.environ.get(
        "AUT_OPENAPI_SPEC"
    )
    if not openapi_path or not os.path.exists(openapi_path):
        missing.append(
            "Verified target OpenAPI / tool specification not found (set NEXACART_OPENAPI_SPEC or AUT_OPENAPI_SPEC)."
        )

    # Check for target authorization / API key
    auth_key = (
        os.environ.get("NEXACART_API_KEY")
        or os.environ.get("AUT_API_KEY")
        or os.environ.get("NEXACART_FIXTURE_RESET_KEY")
    )
    if not auth_key:
        missing.append(
            "Target API credentials/authorization key not found (set NEXACART_API_KEY or AUT_API_KEY)."
        )

    # Architectural safeguard: Live NexaCart adapter connector is not yet implemented or registered in this increment.
    # A configured URL or health check alone does not mark live execution ready.
    missing.append(
        "Live NexaCart adapter connector is not implemented in this pre-live increment. "
        "The connector must implement all 6 required capabilities: "
        + "; ".join(FUTURE_NEXACART_REQUIRED_CAPABILITIES)
    )

    # Live AUT execution is never marked ready in this increment
    return False, missing
