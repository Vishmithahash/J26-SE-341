"""Component 2 Export Facade for Named State Assertions.

Component: C2 - State-Aware Workflow Testing (EFSM)
Responsibilities:
- Evaluates named workflow state assertions against observed runtime evidence/snapshots.
- Preserves three-valued Kleene logic (TRUE, FALSE, UNKNOWN) without collapsing into overall PASS/FAIL.
- Exposes registered domain assertions and custom declarative assertions using C2's predicate evaluator.
- Never manufactures facts when observations are missing or ambiguous.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
    evaluate_predicate,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    LogicalOperator,
    LogicalPredicate,
    PresenceOperator,
    PresencePredicate,
    ScopeEnum,
)
from app.components.c2_state_aware_workflow.predicates.tristate import (
    TriState,
    is_missing,
)


class C2AssertionDefinition(BaseModel):
    """Declarative specification for a named state assertion in C2."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(..., description="Unique assertion identifier")
    assertion_version: str = Field(
        default="1.0.0", description="Semantic assertion version"
    )
    description: str = Field(
        default="", description="Human-readable assertion description"
    )
    predicate: dict[str, Any] = Field(
        ...,
        description="Structured predicate definition compatible with C2 Kleene logic",
    )
    applicable_time_scope: str = Field(
        default="post_recovery",
        description="Expected time scope (e.g. 'post_recovery', 'final_state', 'initial')",
    )
    entity_type: str = Field(default="order", description="Target domain entity type")


class C2AssertionResult(BaseModel):
    """Result of evaluating a named assertion."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    assertion_version: str
    value: TriState
    time_scope: str
    entity_id: str | None = None
    snapshot_id: str | None = None
    evaluator_version: str = "c2_predicates_v1.0"
    provenance: str = "C2_EVALUATOR_BRIDGE"
    details: dict[str, Any] = Field(default_factory=dict)


# Standard declarative assertions registered in C2 for domain workflows
STANDARD_C2_ASSERTIONS: dict[str, C2AssertionDefinition] = {
    "order_created": C2AssertionDefinition(
        assertion_id="order_created",
        assertion_version="1.0.0",
        description="Verifies that an order exists and was not cancelled.",
        predicate=LogicalPredicate(
            op=LogicalOperator.AND,
            clauses=[
                PresencePredicate(
                    target=FieldRef(scope=ScopeEnum.AFTER, path="order.order_id"),
                    op=PresenceOperator.EXISTS,
                ),
                ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="order.status"),
                    op=ComparisonOperator.NOT_EQUALS,
                    right="CANCELLED",
                ),
            ],
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="order",
    ),
    "refund_completed": C2AssertionDefinition(
        assertion_id="refund_completed",
        assertion_version="1.0.0",
        description="Verifies that the refund status reached COMPLETED.",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="refund.status"),
            op=ComparisonOperator.EQUALS,
            right="COMPLETED",
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="refund",
    ),
    "inventory_reserved": C2AssertionDefinition(
        assertion_id="inventory_reserved",
        assertion_version="1.0.0",
        description="Verifies that inventory units were successfully reserved.",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="inventory.reserved"),
            op=ComparisonOperator.EQUALS,
            right=True,
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="inventory",
    ),
    "duplicate_side_effect_detected": C2AssertionDefinition(
        assertion_id="duplicate_side_effect_detected",
        assertion_version="1.0.0",
        description="Evaluates whether any duplicate mutating side-effect occurred.",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="side_effects.duplicate_count"),
            op=ComparisonOperator.GREATER_THAN,
            right=0,
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="side_effects",
    ),
    "idempotency_key_reused": C2AssertionDefinition(
        assertion_id="idempotency_key_reused",
        assertion_version="1.0.0",
        description="Verifies whether a retry safely reused the original idempotency key.",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.EVENT, path="idempotency_key_reused"),
            op=ComparisonOperator.EQUALS,
            right=True,
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="call",
    ),
    "target_idempotency_enforced": C2AssertionDefinition(
        assertion_id="target_idempotency_enforced",
        assertion_version="1.0.0",
        description="Verifies whether target application enforced idempotency guarantees.",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="idempotency.enforced"),
            op=ComparisonOperator.EQUALS,
            right=True,
        ).model_dump(),
        applicable_time_scope="post_recovery",
        entity_type="idempotency",
    ),
}


class C2NamedAssertionEvaluator:
    """Evaluates named assertions using C2's predicate engine without redefining verdicts."""

    EVALUATOR_VERSION = "c2_predicates_v1.0"

    def __init__(
        self,
        custom_registry: dict[str, C2AssertionDefinition] | None = None,
    ):
        self._registry: dict[str, C2AssertionDefinition] = dict(STANDARD_C2_ASSERTIONS)
        if custom_registry:
            self._registry.update(custom_registry)

    def register_assertion(self, assertion: C2AssertionDefinition) -> None:
        """Register or override a named assertion definition."""
        self._registry[assertion.assertion_id] = assertion

    def get_assertion_definition(
        self, assertion_id: str
    ) -> C2AssertionDefinition | None:
        """Look up registered assertion definition by ID."""
        return self._registry.get(assertion_id)

    def list_registered_assertions(self) -> list[str]:
        """List registered assertion IDs."""
        return list(self._registry.keys())

    def evaluate_named_assertion(
        self,
        assertion_id: str,
        observation_context: EvaluationContext,
        time_scope: str = "post_recovery",
        entity_id: str | None = None,
        snapshot_id: str | None = None,
        expected_version: str | None = None,
    ) -> C2AssertionResult:
        """Evaluate a named assertion against an explicit observation context.

        Returns discrete TriState (TRUE, FALSE, UNKNOWN).
        Returns UNKNOWN if assertion is not registered or observation is missing.
        """
        definition = self._registry.get(assertion_id)
        if definition is None:
            return C2AssertionResult(
                assertion_id=assertion_id,
                assertion_version=expected_version or "unknown",
                value=TriState.UNKNOWN,
                time_scope=time_scope,
                entity_id=entity_id,
                snapshot_id=snapshot_id,
                evaluator_version=self.EVALUATOR_VERSION,
                provenance="C2_EVALUATOR_BRIDGE",
                details={"reason": f"Assertion '{assertion_id}' not registered in C2."},
            )

        if expected_version and definition.assertion_version != expected_version:
            return C2AssertionResult(
                assertion_id=assertion_id,
                assertion_version=definition.assertion_version,
                value=TriState.UNKNOWN,
                time_scope=time_scope,
                entity_id=entity_id,
                snapshot_id=snapshot_id,
                evaluator_version=self.EVALUATOR_VERSION,
                provenance="C2_EVALUATOR_BRIDGE",
                details={
                    "reason": (
                        f"Assertion version mismatch for '{assertion_id}': "
                        f"expected '{expected_version}', registered '{definition.assertion_version}'."
                    )
                },
            )

        # If observation scope is completely missing or entity was never observed, return UNKNOWN
        after_scope = observation_context.scopes.get(ScopeEnum.AFTER)
        if after_scope is None or after_scope == {} or is_missing(after_scope):
            return C2AssertionResult(
                assertion_id=definition.assertion_id,
                assertion_version=definition.assertion_version,
                value=TriState.UNKNOWN,
                time_scope=time_scope,
                entity_id=entity_id,
                snapshot_id=snapshot_id,
                evaluator_version=self.EVALUATOR_VERSION,
                provenance="C2_EVALUATOR_BRIDGE",
                details={
                    "reason": "State observation scope 'after' is missing or unobserved."
                },
            )

        if (
            isinstance(after_scope, Mapping)
            and definition.entity_type in after_scope
            and entity_id is not None
        ):
            observed_entity = after_scope.get(definition.entity_type)
            if isinstance(observed_entity, Mapping):
                obs_id = (
                    observed_entity.get(f"{definition.entity_type}_id")
                    or observed_entity.get("id")
                    or observed_entity.get("order_id")
                )
                if obs_id and str(obs_id) != str(entity_id):
                    return C2AssertionResult(
                        assertion_id=definition.assertion_id,
                        assertion_version=definition.assertion_version,
                        value=TriState.UNKNOWN,
                        time_scope=time_scope,
                        entity_id=entity_id,
                        snapshot_id=snapshot_id,
                        evaluator_version=self.EVALUATOR_VERSION,
                        provenance="C2_EVALUATOR_BRIDGE",
                        details={
                            "reason": f"Expected entity '{entity_id}' does not match observed entity '{obs_id}'."
                        },
                    )

        if (
            isinstance(after_scope, Mapping)
            and definition.entity_type not in after_scope
        ):
            return C2AssertionResult(
                assertion_id=definition.assertion_id,
                assertion_version=definition.assertion_version,
                value=TriState.UNKNOWN,
                time_scope=time_scope,
                entity_id=entity_id,
                snapshot_id=snapshot_id,
                evaluator_version=self.EVALUATOR_VERSION,
                provenance="C2_EVALUATOR_BRIDGE",
                details={
                    "reason": (
                        f"Target entity '{definition.entity_type}' was not observed in state snapshot."
                    )
                },
            )

        try:
            val = evaluate_predicate(definition.predicate, observation_context)
        except Exception as exc:  # noqa: BLE001
            val = TriState.UNKNOWN
            details = {"error": str(exc)}
        else:
            details = {"predicate_type": definition.predicate.get("type", "custom")}

        return C2AssertionResult(
            assertion_id=definition.assertion_id,
            assertion_version=definition.assertion_version,
            value=val,
            time_scope=time_scope,
            entity_id=entity_id,
            snapshot_id=snapshot_id,
            evaluator_version=self.EVALUATOR_VERSION,
            provenance="C2_EVALUATOR_BRIDGE",
            details=details,
        )

    def evaluate_assertions_batch(
        self,
        assertion_ids: list[str],
        observation_context: EvaluationContext,
        time_scope: str = "post_recovery",
        entity_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> list[C2AssertionResult]:
        """Evaluate a list of named assertions against the same observation context."""
        return [
            self.evaluate_named_assertion(
                assertion_id=aid,
                observation_context=observation_context,
                time_scope=time_scope,
                entity_id=entity_id,
                snapshot_id=snapshot_id,
            )
            for aid in assertion_ids
        ]
