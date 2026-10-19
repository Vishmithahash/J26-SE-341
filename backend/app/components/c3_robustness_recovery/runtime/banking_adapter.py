"""Banking domain tool adapter and fixture manager for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.

Provides a full DomainToolAdapter and FixtureManager implementation for the second domain
(Financial / Banking wire transfers) to verify adapter generality across domains.
"""

import hashlib
import json
import os
import time
from typing import Any

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CapabilityCombination,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    OccurrenceBounds,
    ReleaseRuleType,
    SafeStr,
    ToolCapabilityDeclaration,
    ToolMutability,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupResult,
    CleanupStatus,
    DomainToolAdapter,
    FixtureManager,
    TargetMode,
    ToolExecutionResult,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    FixtureComparability,
)


class BankingFixtureManager(FixtureManager):
    """Isolated ledger and account state manager for the banking domain."""

    def __init__(self, initial_balance: int = 5000) -> None:
        self._fixture_id = "fix-banking-ledger"
        self._fixture_version = "1.0.0"
        self._initial_balance = initial_balance
        self._namespaces: dict[str, dict[str, Any]] = {}
        self._in_flight: dict[str, int] = {}

    @property
    def fixture_id(self) -> str:
        return self._fixture_id

    @property
    def fixture_version(self) -> str:
        return self._fixture_version

    def prepare_fixture(
        self, namespace: str, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Initialize isolated accounts for a trial namespace."""
        initial = (
            config.get("initial_balance", self._initial_balance)
            if config
            else self._initial_balance
        )
        self._namespaces[namespace] = {
            "source_account": "acc-sender-01",
            "source_balance": initial,
            "target_account": "acc-recipient-02",
            "target_balance": 1000,
            "transfers": [],
            "transfer_count": 0,
            "prepared_at": time.time(),
        }
        self._in_flight[namespace] = 0
        return self.observe_state(namespace)

    def reset_fixture(self, namespace: str) -> None:
        """Reset the given fixture namespace to baseline."""
        if namespace in self._namespaces:
            self._namespaces[namespace]["source_balance"] = self._initial_balance
            self._namespaces[namespace]["target_balance"] = 1000
            self._namespaces[namespace]["transfers"] = []
            self._namespaces[namespace]["transfer_count"] = 0
            self._in_flight[namespace] = 0

    def compute_state_fingerprint(self, state: dict[str, Any]) -> str:
        """Compute a deterministic hash fingerprint of the logical state."""
        canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def observe_state(self, namespace: str) -> dict[str, Any]:
        """Observe ledger balances and transfer count out-of-band."""
        store = self._namespaces.get(namespace)
        if not store:
            return {"error": f"Namespace '{namespace}' not found."}
        return {
            "source_account": store["source_account"],
            "source_balance": store["source_balance"],
            "target_account": store["target_account"],
            "target_balance": store["target_balance"],
            "transfer_count": store["transfer_count"],
            "transfers": list(store["transfers"]),
            "fingerprint": f"bal_{store['source_balance']}_tx_{store['transfer_count']}",
        }

    def verify_committed_transfer(
        self, namespace: str, transfer_reference: str
    ) -> bool:
        """Independently verify whether a specific wire transfer committed."""
        store = self._namespaces.get(namespace)
        if not store:
            return False
        return any(
            t.get("transfer_reference") == transfer_reference
            for t in store.get("transfers", [])
        )

    def compare_states(
        self, baseline_state: dict[str, Any], candidate_state: dict[str, Any]
    ) -> FixtureComparability:
        """Verify that baseline and candidate runs start from identical logical ledger states."""
        b_fp = baseline_state.get("fingerprint")
        c_fp = candidate_state.get("fingerprint")
        if b_fp and b_fp == c_fp:
            return FixtureComparability.EQUIVALENT_LOGICAL_STATE
        return FixtureComparability.NON_EQUIVALENT

    def check_settled(self, namespace: str) -> bool:
        """Check whether all in-flight transfer operations have settled."""
        return self._in_flight.get(namespace, 0) == 0

    def cleanup(self, namespace: str) -> CleanupResult:
        """Safely release and tear down the namespace ledger."""
        if not self.check_settled(namespace):
            in_flight = self._in_flight.get(namespace, 0)
            return CleanupResult(
                status=CleanupStatus.UNCERTAIN,
                details=f"Cleanup uncertain: {in_flight} banking operations still in-flight.",
                reusable=False,
                in_flight_count=in_flight,
            )
        self._namespaces.pop(namespace, None)
        self._in_flight.pop(namespace, None)
        return CleanupResult(
            status=CleanupStatus.CLEANED_AND_VERIFIED,
            details=f"Banking namespace '{namespace}' successfully settled and cleared.",
            reusable=True,
            in_flight_count=0,
        )

    def record_in_flight_start(self, namespace: str) -> None:
        self._in_flight[namespace] = self._in_flight.get(namespace, 0) + 1

    def record_in_flight_end(self, namespace: str) -> None:
        self._in_flight[namespace] = max(0, self._in_flight.get(namespace, 0) - 1)


class BankingServiceAdapter(DomainToolAdapter):
    """Domain tool adapter for banking wire transfers."""

    def __init__(
        self,
        fixture_manager: BankingFixtureManager | None = None,
        target_mode: TargetMode = TargetMode.DEMONSTRATION,
    ) -> None:
        self._fixture_manager = fixture_manager or BankingFixtureManager()
        self._target_mode = target_mode
        self._adapter_id = "adapter-banking-transfer-01"
        self._adapter_version = "1.0.0"

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def adapter_version(self) -> str:
        return self._adapter_version

    @property
    def target_mode(self) -> TargetMode:
        return self._target_mode

    def get_manifest(self) -> AdapterCapabilityManifest:
        """Return the declared capabilities for the banking domain tool."""
        return AdapterCapabilityManifest(
            adapter_id=SafeStr(self._adapter_id),
            adapter_version=SafeStr(self._adapter_version),
            schema_version=SafeStr("1.0.0"),
            tools=[
                ToolCapabilityDeclaration(
                    tool_id=SafeStr("wire_transfer"),
                    tool_version=SafeStr("1.0.0"),
                    mutability=ToolMutability.SIDE_EFFECTING,
                )
            ],
            supported_combinations=[
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=5
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[
                        SafeStr("CALLER_TIMEOUT_EXCEEDED"),
                        SafeStr("HANG_INDEFINITELY"),
                    ],
                    required_observation_capabilities=[SafeStr("transfer_latency_ms")],
                ),
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                    effect_phase=EffectPhase.AFTER_COMMIT,
                    interception_hook=InterceptionHook.APPLICATION_AWARE_HOOK,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=3
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[SafeStr("CALLER_TIMEOUT_EXCEEDED")],
                    required_observation_capabilities=[
                        SafeStr("transfer_latency_ms"),
                        SafeStr("independent_commit_observation"),
                    ],
                ),
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.TRANSIENT_5XX,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=5
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[
                        SafeStr("HTTP_500"),
                        SafeStr("HTTP_503"),
                    ],
                    required_observation_capabilities=[SafeStr("http_status_code")],
                ),
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.RATE_LIMIT_429,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=5
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[
                        SafeStr("HTTP_429_WITH_RETRY_AFTER"),
                        SafeStr("HTTP_429_NO_RETRY_AFTER"),
                    ],
                    required_observation_capabilities=[SafeStr("http_status_code")],
                ),
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.TOOL_UNAVAILABILITY,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=5
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[SafeStr("SERVICE_MAINTENANCE")],
                    required_observation_capabilities=[SafeStr("error_message")],
                ),
                CapabilityCombination(
                    tool_id=SafeStr("wire_transfer"),
                    fault_family=FaultFamily.MALFORMED_RESPONSE,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    supported_occurrence_bounds=OccurrenceBounds(
                        min_occurrence=1, max_occurrence=5
                    ),
                    allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                    supported_payload_modes=[SafeStr("SCHEMA_VIOLATION")],
                    required_observation_capabilities=[SafeStr("payload_bytes")],
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
        """Execute wire_transfer against isolated ledger."""
        start_time = time.perf_counter()
        namespace = (call_context or {}).get("namespace", "default_banking_ns")

        self._fixture_manager.record_in_flight_start(namespace)
        try:
            amount = int(arguments.get("amount", 500))
            ref = (
                arguments.get("transfer_reference")
                or f"tx-demo-{int(time.time() * 1000)}"
            )

            store = self._fixture_manager._namespaces.get(namespace)
            if not store:
                return ToolExecutionResult(
                    success=False,
                    tool_id=tool_id,
                    tool_version=tool_version,
                    error=f"Namespace '{namespace}' not found.",
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                )

            if store["source_balance"] < amount:
                return ToolExecutionResult(
                    success=False,
                    tool_id=tool_id,
                    tool_version=tool_version,
                    error="Insufficient funds in source account.",
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                )

            # Apply atomic ledger mutation
            store["source_balance"] -= amount
            store["target_balance"] += amount
            tx_record = {
                "transfer_reference": ref,
                "amount": amount,
                "status": "SETTLED",
                "timestamp": time.time(),
            }
            store["transfers"].append(tx_record)
            store["transfer_count"] += 1

            latency = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResult(
                success=True,
                tool_id=tool_id,
                tool_version=tool_version,
                output={
                    "transfer_reference": ref,
                    "status": "SETTLED",
                    "transferred_amount": amount,
                    "remaining_source_balance": store["source_balance"],
                },
                latency_ms=latency,
                side_effect_occurred=True,
                idempotency_key=arguments.get("idempotency_key"),
            )
        finally:
            self._fixture_manager.record_in_flight_end(namespace)


def check_two_domain_prerequisites() -> dict[str, Any]:
    """Check live target and agent prerequisites across both research domains."""
    from app.components.c3_robustness_recovery.runtime.adapter import (
        check_real_target_prerequisites,
    )

    ecommerce_available, ecommerce_missing = check_real_target_prerequisites()

    # Banking live prerequisites check
    banking_missing: list[str] = []
    banking_url = os.environ.get("BANKING_TARGET_URL") or os.environ.get(
        "BANKING_AUT_URL"
    )
    if not banking_url:
        banking_missing.append(
            "Banking domain live endpoint not configured (set BANKING_TARGET_URL)."
        )
    banking_spec = os.environ.get("BANKING_OPENAPI_SPEC")
    if not banking_spec or not os.path.exists(banking_spec):
        banking_missing.append(
            "Banking domain OpenAPI specification not found (set BANKING_OPENAPI_SPEC)."
        )
    banking_key = os.environ.get("BANKING_API_KEY")
    if not banking_key:
        banking_missing.append(
            "Banking domain API authorization key not found (set BANKING_API_KEY)."
        )

    banking_available = len(banking_missing) == 0

    return {
        "ecommerce_domain": {
            "name": "NexaCart E-Commerce",
            "is_available": ecommerce_available,
            "missing_prerequisites": ecommerce_missing,
            "status": "READY" if ecommerce_available else "BLOCKED",
        },
        "banking_domain": {
            "name": "Financial Wire Transfer",
            "is_available": banking_available,
            "missing_prerequisites": banking_missing,
            "status": "READY" if banking_available else "BLOCKED",
        },
        "two_domain_live_ready": ecommerce_available and banking_available,
    }
