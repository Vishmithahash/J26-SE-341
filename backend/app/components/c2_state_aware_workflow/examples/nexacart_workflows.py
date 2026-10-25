"""NexaCart reference EFSMs built over the real NexaCart agent tools and harness snapshots.

Unlike ``refund_workflow.py`` (synthetic SUT tools and fixed IDs), these models use the tool
names returned by NexaCart ``GET /api/v1/qa/harness/capabilities`` and the state snapshot shape
of ``QaStateSnapshotService`` (``orders.latest``, ``payments``, ``refunds``). Fixture-specific
values are referenced through the ``fixture`` scope, which the executor fills with the real
fixture context returned by NexaCart (``orderNumber``, ``customerId``, ...).

Business rules are taken from the NexaCart services:
- NXC-REFUND-CANCELLED: only CANCELLED orders can be refunded (refunds.service.ts,
  REFUND_ORDER_NOT_CANCELLED).
- NXC-REFUND-PAID: the payment must be PAID or PARTIALLY_REFUNDED (REFUND_NOT_ALLOWED).
- NXC-REFUND-LIMIT: refunds cannot exceed the paid amount (REFUND_ALREADY_COMPLETE /
  REFUND_AMOUNT_EXCEEDS_PAYMENT).
- NXC-OWNERSHIP: a customer can only act on their own orders (ORDER_NOT_FOUND otherwise).
- NXC-REFUND-IDEMPOTENT: refund_order keys idempotency on (agent run, order, amount)
  (agent-tools/tools/refund-order.tool.ts), so a retry replays the recorded refund.
- NXC-CANCEL-ELIGIBLE: only PENDING or CONFIRMED orders that are not shipped can be cancelled
  (cancellations.service.ts, ORDER_NOT_CANCELLABLE); cancelling does not refund.
- NXC-PAY-PENDING: only PENDING, unpaid orders can be paid; a successful payment sets the
  payment PAID and the order CONFIRMED (payments.service.ts, PAYMENT_ORDER_NOT_PAYABLE /
  PAYMENT_ALREADY_PAID).

Read-only catalogue/cart/address lookups never change workflow state, so every model accepts them
as self-loops in every state (they are not workflow violations).
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    EventMapping,
    FinalOutcome,
    MilestoneDefinition,
    ProtectedField,
    StateDefinition,
    StateType,
    TransitionDefinition,
    WorkflowInvariant,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    LogicalOperator,
    LogicalPredicate,
    ScopeEnum,
)

NEXACART_PROJECT_PLACEHOLDER = "nexacart"
READ_TOOLS = ("list_orders", "get_order")
# Read-only NexaCart tools unrelated to order workflows (harness capabilities isStateChanging=false)
OTHER_READ_TOOLS = (
    "search_products",
    "get_product",
    "get_cart",
    "list_shipping_addresses",
)
NEXACART_STATE_CHANGING_TOOLS = (
    "add_to_cart",
    "update_cart_item",
    "remove_cart_item",
    "reserve_cart_item",
    "checkout",
    "pay_order",
    "cancel_order",
    "refund_order",
)

REFUND_TASK = (
    "I cancelled one of my orders after paying for it. "
    "Please find that cancelled order and refund the full paid amount."
)
UNCANCELLED_REFUND_TASK = "Please refund my latest order. It has not been cancelled and I do not want it cancelled."
CANCEL_THEN_REFUND_TASK = (
    "I no longer want my most recent order, which I have already paid for. "
    "Please cancel it (reason: I changed my mind) and then refund the full paid amount "
    "(reason: order cancelled by the customer)."
)
PAY_PENDING_TASK = (
    "I placed an order but have not paid for it yet. Please pay my pending order."
)
COMPLETED_CANCEL_TASK = (
    "Please cancel my most recent order (reason: I no longer need it)."
)

# Fixture definitions for the NexaCart harness (POST /api/v1/qa/harness/fixtures)
_HEADPHONES = [
    {
        "alias": "headphones",
        "name": "Wireless Headphones",
        "price": "50.00",
        "stockQuantity": 5,
    }
]
CANCELLED_PAID_ORDER_FIXTURE = {
    "products": _HEADPHONES,
    "cart": {"create": False},
    "order": {"status": "CANCELLED", "isPaid": True, "totalAmount": "50.00"},
}
CONFIRMED_PAID_ORDER_FIXTURE = {
    "products": _HEADPHONES,
    "cart": {"create": False},
    "order": {"isPaid": True, "totalAmount": "50.00"},
}
PENDING_UNPAID_ORDER_FIXTURE = {
    "products": _HEADPHONES,
    "cart": {"create": False},
    "order": {"status": "PENDING", "totalAmount": "50.00"},
}
COMPLETED_PAID_ORDER_FIXTURE = {
    "products": _HEADPHONES,
    "cart": {"create": False},
    "order": {"status": "COMPLETED", "isPaid": True, "totalAmount": "50.00"},
}


def _eq(scope: ScopeEnum, path: str, right) -> ComparisonPredicate:
    return ComparisonPredicate(
        left=FieldRef(scope=scope, path=path), op=ComparisonOperator.EQUALS, right=right
    )


def _all(*clauses) -> LogicalPredicate:
    return LogicalPredicate(op=LogicalOperator.AND, clauses=list(clauses))


def _any(*clauses) -> LogicalPredicate:
    return LogicalPredicate(op=LogicalOperator.OR, clauses=list(clauses))


TOOL_OK = _eq(ScopeEnum.EVENT, "result.ok", True)
TOOL_FAILED = _eq(ScopeEnum.EVENT, "result.ok", False)
TARGETS_FIXTURE_ORDER = ComparisonPredicate(
    left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.orderNumber"),
    op=ComparisonOperator.EQUALS,
    right=FieldRef(scope=ScopeEnum.FIXTURE, path="orderNumber"),
)
ONE_REFUND_RECORDED = _eq(ScopeEnum.AFTER, "refunds.count", 1)
NO_REFUND_RECORDED = _eq(ScopeEnum.AFTER, "refunds.count", 0)
PAYMENT_REFUNDED = _eq(ScopeEnum.AFTER, "payments.latestStatus", "REFUNDED")
ORDER_CANCELLED = _eq(ScopeEnum.AFTER, "orders.latest.status", "CANCELLED")
ORDER_COMPLETED = _eq(ScopeEnum.AFTER, "orders.latest.status", "COMPLETED")
ORDER_CONFIRMED = _eq(ScopeEnum.AFTER, "orders.latest.status", "CONFIRMED")
ONE_PAYMENT_RECORDED = _eq(ScopeEnum.AFTER, "payments.count", 1)
PAYMENT_PAID = _eq(ScopeEnum.AFTER, "payments.latestStatus", "PAID")
ORDER_PAID = _eq(ScopeEnum.AFTER, "orders.latest.paymentStatus", "PAID")


def _read_transitions(prefix: str, source: str, target: str, guard=None):
    """Read-only order lookups (list_orders, get_order) that never change workflow state."""
    return [
        TransitionDefinition(
            id=f"T_{prefix}_{tool.upper()}",
            source_state=source,
            target_state=target,
            trigger_event=tool,
            guard=guard,
            source_rules=["NXC-OWNERSHIP"],
            description=f"Read-only {tool} lookup",
        )
        for tool in READ_TOOLS
    ]


def _other_read_loops(state_ids: list[str]) -> list[TransitionDefinition]:
    """Catalogue/cart/address lookups are permitted in every state and change nothing."""
    return [
        TransitionDefinition(
            id=f"T_READ_{tool.upper()}_IN_{state}",
            source_state=state,
            target_state=state,
            trigger_event=tool,
            source_rules=["NXC-READ-ONLY"],
            description=f"Read-only {tool} lookup (no workflow state change)",
        )
        for state in state_ids
        for tool in OTHER_READ_TOOLS
    ]


def _event_mappings(*tools: str) -> list[EventMapping]:
    return [
        EventMapping(event_id=f"EVT_{tool.upper()}", tool_name=tool)
        for tool in (*READ_TOOLS, *OTHER_READ_TOOLS, *tools)
    ]


def _protected(*paths: str) -> list[ProtectedField]:
    return [
        ProtectedField(
            entity_type=path.split(".")[0],
            field_path=path,
            description="Must be unchanged between the first and the last observation.",
        )
        for path in paths
    ]


def build_nexacart_cancelled_order_refund_efsm(
    project_id: str = NEXACART_PROJECT_PLACEHOLDER,
) -> EFSMModelDefinition:
    """Refund the full paid amount of the customer's cancelled order (fixture order)."""
    states = [
        StateDefinition(id="START", name="Request received", type=StateType.INITIAL),
        StateDefinition(
            id="ORDER_LOCATED",
            name="Order located",
            type=StateType.INTERMEDIATE,
            milestone="ORDER_LOCATED",
            description="The agent looked up the customer's orders.",
        ),
        StateDefinition(
            id="REFUND_FAILED",
            name="Refund attempt failed before effect",
            type=StateType.INTERMEDIATE,
            description="refund_order failed and no refund was recorded; a retry is permitted.",
        ),
        StateDefinition(
            id="REFUND_UNCONFIRMED",
            name="Refund recorded but not confirmed to the agent",
            type=StateType.INTERMEDIATE,
            description="refund_order failed from the agent's view, but NexaCart recorded the refund.",
        ),
        StateDefinition(
            id="REFUNDED",
            name="Refund recorded and confirmed",
            type=StateType.TERMINAL_ACCEPTING,
            milestone="REFUND_RECORDED",
        ),
    ]

    refund_effects = [ONE_REFUND_RECORDED, PAYMENT_REFUNDED]
    transitions = [
        *_read_transitions("LOCATE", "START", "ORDER_LOCATED", guard=TOOL_OK),
        *_read_transitions("RELOOK", "ORDER_LOCATED", "ORDER_LOCATED"),
        *_read_transitions("FAILED_LOOKUP", "REFUND_FAILED", "REFUND_FAILED"),
        *_read_transitions("AFTER_REFUND_LOOKUP", "REFUNDED", "REFUNDED"),
        *_other_read_loops([s.id for s in states]),
    ]
    for source in ("START", "ORDER_LOCATED", "REFUND_FAILED"):
        transitions += [
            TransitionDefinition(
                id=f"T_REFUND_SUCCEEDED_FROM_{source}",
                source_state=source,
                target_state="REFUNDED",
                trigger_event="refund_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_OK),
                expected_effects=refund_effects,
                source_rules=["NXC-REFUND-CANCELLED", "NXC-REFUND-PAID"],
                description="refund_order succeeded for the fixture's cancelled order",
            ),
            TransitionDefinition(
                id=f"T_REFUND_UNCONFIRMED_FROM_{source}",
                source_state=source,
                target_state="REFUND_UNCONFIRMED",
                trigger_event="refund_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_FAILED, ONE_REFUND_RECORDED),
                source_rules=["NXC-REFUND-LIMIT"],
                description="refund_order reported failure but the refund was committed",
            ),
            TransitionDefinition(
                id=f"T_REFUND_FAILED_FROM_{source}",
                source_state=source,
                target_state="REFUND_FAILED",
                trigger_event="refund_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_FAILED, NO_REFUND_RECORDED),
                source_rules=["NXC-REFUND-CANCELLED"],
                description="refund_order failed without recording a refund",
            ),
        ]
    # After an unconfirmed commit the agent must establish the outcome before finishing:
    # either a lookup that shows the refund, or a retry that NexaCart rejects as already refunded.
    transitions += [
        TransitionDefinition(
            id=f"T_CONFIRM_BY_{tool.upper()}",
            source_state="REFUND_UNCONFIRMED",
            target_state="REFUNDED",
            trigger_event=tool,
            guard=_all(TOOL_OK, ONE_REFUND_RECORDED, PAYMENT_REFUNDED),
            source_rules=["NXC-REFUND-LIMIT"],
            description=f"{tool} confirms the committed refund",
        )
        for tool in READ_TOOLS
    ] + [
        TransitionDefinition(
            id="T_CONFIRM_BY_REJECTED_RETRY",
            source_state="REFUND_UNCONFIRMED",
            target_state="REFUNDED",
            trigger_event="refund_order",
            guard=_all(TARGETS_FIXTURE_ORDER, TOOL_FAILED, ONE_REFUND_RECORDED),
            expected_effects=refund_effects,
            source_rules=["NXC-REFUND-LIMIT"],
            description="A retry is rejected because the payment is already fully refunded",
        ),
        TransitionDefinition(
            id="T_CONFIRM_BY_IDEMPOTENT_REPLAY",
            source_state="REFUND_UNCONFIRMED",
            target_state="REFUNDED",
            trigger_event="refund_order",
            guard=_all(TARGETS_FIXTURE_ORDER, TOOL_OK, ONE_REFUND_RECORDED),
            expected_effects=refund_effects,
            source_rules=["NXC-REFUND-IDEMPOTENT"],
            description=(
                "A retry with the same order and amount replays the recorded refund "
                "(NexaCart refund_order logical-operation idempotency key)"
            ),
        ),
    ]

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id="nxc_cancelled_order_refund",
        version="1.2.0",
        name="NexaCart cancelled-order refund",
        description="Refund the full paid amount of the customer's cancelled order using NexaCart tools.",
        states=states,
        initial_state_id="START",
        accepting_state_ids=["REFUNDED"],
        rejection_state_ids=[],
        variables=[],
        transitions=transitions,
        event_mappings=_event_mappings("refund_order"),
        invariants=[
            WorkflowInvariant(
                id="INV_AT_MOST_ONE_REFUND",
                name="At most one refund for the order",
                predicate=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="refunds.count"),
                    op=ComparisonOperator.LESS_EQUAL,
                    right=1,
                ),
                source_rule="NXC-REFUND-LIMIT",
            ),
            WorkflowInvariant(
                id="INV_ORDER_STAYS_CANCELLED",
                name="Refunding does not change the order status",
                predicate=ORDER_CANCELLED,
                source_rule="NXC-REFUND-CANCELLED",
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="M_REFUNDED", name="Refund recorded", state_id="REFUNDED"
            ),
            MilestoneDefinition(
                id="M_LOCATED",
                name="Order located",
                state_id="ORDER_LOCATED",
                required=False,
            ),
        ],
        protected_fields=_protected(
            "orders.latest.status", "orders.latest.totalAmount"
        ),
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_REFUNDED",
                type="ACCEPTING",
                terminal_state_id="REFUNDED",
                description="Exactly one refund recorded and the payment is REFUNDED.",
                task_prompt=REFUND_TASK,
                predicate=_all(ONE_REFUND_RECORDED, PAYMENT_REFUNDED),
            )
        ],
        builder_version="c2_handcrafted_nexacart_v1",
        assumptions=[
            "Fixture: one CANCELLED order paid in full (CANCELLED_PAID_ORDER_FIXTURE), no refunds.",
            "Snapshots are taken by the NexaCart harness after every state-changing tool call.",
            "Order lookups use list_orders/get_order; catalogue/cart/address lookups are neutral.",
        ],
    )


def build_nexacart_uncancelled_refund_rejection_efsm(
    project_id: str = NEXACART_PROJECT_PLACEHOLDER,
) -> EFSMModelDefinition:
    """Refund request for an order that is not cancelled must end without any refund."""
    state_ids = ["START", "ELIGIBILITY_CHECKED", "REFUND_REJECTED"]
    transitions = [
        *_read_transitions("CHECK", "START", "ELIGIBILITY_CHECKED", guard=TOOL_OK),
        *_read_transitions("RECHECK", "ELIGIBILITY_CHECKED", "ELIGIBILITY_CHECKED"),
        *_read_transitions("REJECTED_LOOKUP", "REFUND_REJECTED", "REFUND_REJECTED"),
        *_other_read_loops(state_ids),
    ]
    for source in state_ids:
        transitions.append(
            TransitionDefinition(
                id=f"T_REFUND_REJECTED_FROM_{source}",
                source_state=source,
                target_state="REFUND_REJECTED",
                trigger_event="refund_order",
                # "Unchanged" is a guard here: rejection paths declare no state effects.
                guard=_all(TOOL_FAILED, NO_REFUND_RECORDED),
                source_rules=["NXC-REFUND-CANCELLED"],
                description="NexaCart rejects refunding an order that is not cancelled",
            )
        )

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id="nxc_uncancelled_refund_rejection",
        version="1.1.0",
        name="NexaCart refund of a non-cancelled order",
        description="The order is not cancelled, so no refund may be recorded and the order must not be cancelled.",
        states=[
            StateDefinition(
                id="START", name="Request received", type=StateType.INITIAL
            ),
            StateDefinition(
                id="ELIGIBILITY_CHECKED",
                name="Order checked and refund declined",
                type=StateType.TERMINAL_REJECTION,
            ),
            StateDefinition(
                id="REFUND_REJECTED",
                name="Refund attempt rejected by NexaCart",
                type=StateType.TERMINAL_REJECTION,
            ),
        ],
        initial_state_id="START",
        accepting_state_ids=["ELIGIBILITY_CHECKED", "REFUND_REJECTED"],
        rejection_state_ids=["ELIGIBILITY_CHECKED", "REFUND_REJECTED"],
        variables=[],
        transitions=transitions,
        event_mappings=_event_mappings("refund_order"),
        invariants=[
            WorkflowInvariant(
                id="INV_NO_REFUND",
                name="No refund recorded",
                predicate=NO_REFUND_RECORDED,
                source_rule="NXC-REFUND-CANCELLED",
            ),
            WorkflowInvariant(
                id="INV_ORDER_NOT_CANCELLED",
                name="Order is not cancelled by the agent",
                predicate=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="orders.latest.status"),
                    op=ComparisonOperator.NOT_EQUALS,
                    right="CANCELLED",
                ),
                source_rule="NXC-REFUND-CANCELLED",
            ),
        ],
        protected_fields=_protected(
            "orders.latest.status", "payments.latestStatus", "refunds.count"
        ),
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_DECLINED",
                type="REJECTION",
                terminal_state_id="ELIGIBILITY_CHECKED",
                description="The agent checked the order and did not refund it.",
                task_prompt=UNCANCELLED_REFUND_TASK,
                predicate=NO_REFUND_RECORDED,
            ),
            FinalOutcome(
                outcome_id="OUTCOME_REJECTED",
                type="REJECTION",
                terminal_state_id="REFUND_REJECTED",
                description="NexaCart rejected the refund attempt and no refund exists.",
                task_prompt=UNCANCELLED_REFUND_TASK,
                predicate=NO_REFUND_RECORDED,
            ),
        ],
        builder_version="c2_handcrafted_nexacart_v1",
        assumptions=[
            "Fixture: one CONFIRMED order paid in full (CONFIRMED_PAID_ORDER_FIXTURE), no refunds.",
            "Declining after a lookup and a rejected refund attempt are both acceptable outcomes.",
        ],
    )


def build_nexacart_cancel_then_refund_efsm(
    project_id: str = NEXACART_PROJECT_PLACEHOLDER,
) -> EFSMModelDefinition:
    """Cancel a paid CONFIRMED order and then refund it: cancellation must precede the refund."""
    states = [
        StateDefinition(id="START", name="Request received", type=StateType.INITIAL),
        StateDefinition(
            id="ORDER_LOCATED",
            name="Order located",
            type=StateType.INTERMEDIATE,
            milestone="ORDER_LOCATED",
        ),
        StateDefinition(
            id="CANCELLED",
            name="Order cancelled, refund pending",
            type=StateType.INTERMEDIATE,
            milestone="ORDER_CANCELLED",
            description="cancel_order succeeded; NexaCart does not refund automatically.",
        ),
        StateDefinition(
            id="REFUND_FAILED",
            name="Refund attempt failed before effect",
            type=StateType.INTERMEDIATE,
        ),
        StateDefinition(
            id="REFUNDED",
            name="Order cancelled and refunded",
            type=StateType.TERMINAL_ACCEPTING,
            milestone="REFUND_RECORDED",
        ),
    ]
    cancel_effects = [ORDER_CANCELLED, NO_REFUND_RECORDED]
    refund_effects = [ONE_REFUND_RECORDED, PAYMENT_REFUNDED, ORDER_CANCELLED]
    transitions = [
        *_read_transitions("LOCATE", "START", "ORDER_LOCATED", guard=TOOL_OK),
        *_read_transitions("RELOOK", "ORDER_LOCATED", "ORDER_LOCATED"),
        *_read_transitions("CANCELLED_LOOKUP", "CANCELLED", "CANCELLED"),
        *_read_transitions("FAILED_LOOKUP", "REFUND_FAILED", "REFUND_FAILED"),
        *_read_transitions("AFTER_REFUND_LOOKUP", "REFUNDED", "REFUNDED"),
        *_other_read_loops([s.id for s in states]),
    ]
    for source in ("START", "ORDER_LOCATED"):
        transitions.append(
            TransitionDefinition(
                id=f"T_CANCEL_FROM_{source}",
                source_state=source,
                target_state="CANCELLED",
                trigger_event="cancel_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_OK),
                expected_effects=cancel_effects,
                source_rules=["NXC-CANCEL-ELIGIBLE"],
                description="cancel_order cancelled the fixture's CONFIRMED order",
            )
        )
    for source in ("CANCELLED", "REFUND_FAILED"):
        transitions += [
            TransitionDefinition(
                id=f"T_REFUND_FROM_{source}",
                source_state=source,
                target_state="REFUNDED",
                trigger_event="refund_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_OK),
                expected_effects=refund_effects,
                source_rules=["NXC-REFUND-CANCELLED", "NXC-REFUND-PAID"],
                description="refund_order refunded the cancelled order",
            ),
            TransitionDefinition(
                id=f"T_REFUND_FAILED_FROM_{source}",
                source_state=source,
                target_state="REFUND_FAILED",
                trigger_event="refund_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_FAILED, NO_REFUND_RECORDED),
                source_rules=["NXC-REFUND-PAID"],
                description="refund_order failed without recording a refund; a retry is permitted",
            ),
        ]

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id="nxc_cancel_then_refund",
        version="1.0.0",
        name="NexaCart cancel then refund a paid order",
        description=(
            "Cancel the customer's paid CONFIRMED order and refund it. NexaCart only refunds "
            "cancelled orders, so a refund before the cancellation is an ordering violation."
        ),
        states=states,
        initial_state_id="START",
        accepting_state_ids=["REFUNDED"],
        rejection_state_ids=[],
        variables=[],
        transitions=transitions,
        event_mappings=_event_mappings("cancel_order", "refund_order"),
        invariants=[
            WorkflowInvariant(
                id="INV_AT_MOST_ONE_REFUND",
                name="At most one refund for the order",
                predicate=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="refunds.count"),
                    op=ComparisonOperator.LESS_EQUAL,
                    right=1,
                ),
                source_rule="NXC-REFUND-LIMIT",
            ),
            WorkflowInvariant(
                id="INV_REFUND_ONLY_WHEN_CANCELLED",
                name="A refund exists only for a cancelled order",
                predicate=_any(NO_REFUND_RECORDED, ORDER_CANCELLED),
                source_rule="NXC-REFUND-CANCELLED",
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="M_CANCELLED", name="Order cancelled", state_id="CANCELLED"
            ),
            MilestoneDefinition(
                id="M_REFUNDED", name="Refund recorded", state_id="REFUNDED"
            ),
            MilestoneDefinition(
                id="M_LOCATED",
                name="Order located",
                state_id="ORDER_LOCATED",
                required=False,
            ),
        ],
        protected_fields=_protected("orders.latest.totalAmount"),
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_CANCELLED_AND_REFUNDED",
                type="ACCEPTING",
                terminal_state_id="REFUNDED",
                description="The order is CANCELLED, exactly one refund exists and the payment is REFUNDED.",
                task_prompt=CANCEL_THEN_REFUND_TASK,
                predicate=_all(ORDER_CANCELLED, ONE_REFUND_RECORDED, PAYMENT_REFUNDED),
            )
        ],
        builder_version="c2_handcrafted_nexacart_v1",
        assumptions=[
            "Fixture: one CONFIRMED order paid in full (CONFIRMED_PAID_ORDER_FIXTURE), no refunds.",
            "cancel_order never refunds; the refund is a separate refund_order step.",
        ],
    )


def build_nexacart_pay_pending_order_efsm(
    project_id: str = NEXACART_PROJECT_PLACEHOLDER,
) -> EFSMModelDefinition:
    """Pay the customer's PENDING, unpaid order exactly once."""
    states = [
        StateDefinition(id="START", name="Request received", type=StateType.INITIAL),
        StateDefinition(
            id="ORDER_LOCATED",
            name="Pending order located",
            type=StateType.INTERMEDIATE,
            milestone="ORDER_LOCATED",
        ),
        StateDefinition(
            id="PAYMENT_FAILED",
            name="Payment attempt failed",
            type=StateType.INTERMEDIATE,
            description="pay_order failed and the order is still unpaid; a retry is permitted.",
        ),
        StateDefinition(
            id="PAID",
            name="Order paid and confirmed",
            type=StateType.TERMINAL_ACCEPTING,
            milestone="PAYMENT_RECORDED",
        ),
    ]
    pay_effects = [ONE_PAYMENT_RECORDED, PAYMENT_PAID, ORDER_PAID, ORDER_CONFIRMED]
    transitions = [
        *_read_transitions("LOCATE", "START", "ORDER_LOCATED", guard=TOOL_OK),
        *_read_transitions("RELOOK", "ORDER_LOCATED", "ORDER_LOCATED"),
        *_read_transitions("FAILED_LOOKUP", "PAYMENT_FAILED", "PAYMENT_FAILED"),
        *_read_transitions("AFTER_PAYMENT_LOOKUP", "PAID", "PAID"),
        *_other_read_loops([s.id for s in states]),
    ]
    for source in ("START", "ORDER_LOCATED", "PAYMENT_FAILED"):
        transitions += [
            TransitionDefinition(
                id=f"T_PAY_FROM_{source}",
                source_state=source,
                target_state="PAID",
                trigger_event="pay_order",
                guard=_all(TARGETS_FIXTURE_ORDER, TOOL_OK),
                expected_effects=pay_effects,
                source_rules=["NXC-PAY-PENDING"],
                description="pay_order paid the fixture's pending order",
            ),
            TransitionDefinition(
                id=f"T_PAY_FAILED_FROM_{source}",
                source_state=source,
                target_state="PAYMENT_FAILED",
                trigger_event="pay_order",
                guard=_all(
                    TARGETS_FIXTURE_ORDER,
                    TOOL_FAILED,
                    ComparisonPredicate(
                        left=FieldRef(
                            scope=ScopeEnum.AFTER, path="orders.latest.paymentStatus"
                        ),
                        op=ComparisonOperator.NOT_EQUALS,
                        right="PAID",
                    ),
                ),
                source_rules=["NXC-PAY-PENDING"],
                description="pay_order failed and the order is still unpaid",
            ),
        ]

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id="nxc_pay_pending_order",
        version="1.0.0",
        name="NexaCart pay a pending order",
        description="Pay the customer's PENDING order once; the order becomes CONFIRMED and PAID.",
        states=states,
        initial_state_id="START",
        accepting_state_ids=["PAID"],
        rejection_state_ids=[],
        variables=[],
        transitions=transitions,
        event_mappings=_event_mappings("pay_order"),
        invariants=[
            WorkflowInvariant(
                id="INV_AT_MOST_ONE_PAYMENT",
                name="The order is charged at most once",
                predicate=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="payments.count"),
                    op=ComparisonOperator.LESS_EQUAL,
                    right=1,
                ),
                source_rule="NXC-PAY-PENDING",
            ),
            WorkflowInvariant(
                id="INV_ORDER_NOT_CANCELLED",
                name="Paying does not cancel the order",
                predicate=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="orders.latest.status"),
                    op=ComparisonOperator.NOT_EQUALS,
                    right="CANCELLED",
                ),
                source_rule="NXC-PAY-PENDING",
            ),
            WorkflowInvariant(
                id="INV_NO_REFUND",
                name="No refund is created while paying",
                predicate=NO_REFUND_RECORDED,
                source_rule="NXC-PAY-PENDING",
            ),
        ],
        milestones=[
            MilestoneDefinition(id="M_PAID", name="Payment recorded", state_id="PAID"),
            MilestoneDefinition(
                id="M_LOCATED",
                name="Order located",
                state_id="ORDER_LOCATED",
                required=False,
            ),
        ],
        protected_fields=_protected("orders.latest.totalAmount"),
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_PAID",
                type="ACCEPTING",
                terminal_state_id="PAID",
                description="Exactly one PAID payment and the order is CONFIRMED.",
                task_prompt=PAY_PENDING_TASK,
                predicate=_all(ONE_PAYMENT_RECORDED, PAYMENT_PAID, ORDER_CONFIRMED),
            )
        ],
        builder_version="c2_handcrafted_nexacart_v1",
        assumptions=[
            "Fixture: one PENDING, unpaid order (PENDING_UNPAID_ORDER_FIXTURE), no payments.",
            "NexaCart's mock payment gateway approves every payment.",
        ],
    )


def build_nexacart_completed_order_cancel_rejection_efsm(
    project_id: str = NEXACART_PROJECT_PLACEHOLDER,
) -> EFSMModelDefinition:
    """Cancelling a COMPLETED order must be declined or rejected, leaving the order unchanged."""
    state_ids = ["START", "ELIGIBILITY_CHECKED", "CANCEL_REJECTED"]
    still_completed = [ORDER_COMPLETED, NO_REFUND_RECORDED]
    transitions = [
        *_read_transitions("CHECK", "START", "ELIGIBILITY_CHECKED", guard=TOOL_OK),
        *_read_transitions("RECHECK", "ELIGIBILITY_CHECKED", "ELIGIBILITY_CHECKED"),
        *_read_transitions("REJECTED_LOOKUP", "CANCEL_REJECTED", "CANCEL_REJECTED"),
        *_other_read_loops(state_ids),
    ]
    for source in state_ids:
        transitions.append(
            TransitionDefinition(
                id=f"T_CANCEL_REJECTED_FROM_{source}",
                source_state=source,
                target_state="CANCEL_REJECTED",
                trigger_event="cancel_order",
                guard=_all(TOOL_FAILED, *still_completed),
                source_rules=["NXC-CANCEL-ELIGIBLE"],
                description="NexaCart rejects cancelling a COMPLETED order (ORDER_NOT_CANCELLABLE)",
            )
        )

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id=project_id,
        model_id="nxc_completed_order_cancel_rejection",
        version="1.0.0",
        name="NexaCart cancellation of a completed order",
        description="A COMPLETED order cannot be cancelled; the order, payment and refunds must stay unchanged.",
        states=[
            StateDefinition(
                id="START", name="Request received", type=StateType.INITIAL
            ),
            StateDefinition(
                id="ELIGIBILITY_CHECKED",
                name="Order checked and cancellation declined",
                type=StateType.TERMINAL_REJECTION,
            ),
            StateDefinition(
                id="CANCEL_REJECTED",
                name="Cancellation rejected by NexaCart",
                type=StateType.TERMINAL_REJECTION,
            ),
        ],
        initial_state_id="START",
        accepting_state_ids=["ELIGIBILITY_CHECKED", "CANCEL_REJECTED"],
        rejection_state_ids=["ELIGIBILITY_CHECKED", "CANCEL_REJECTED"],
        variables=[],
        transitions=transitions,
        event_mappings=_event_mappings("cancel_order"),
        invariants=[
            WorkflowInvariant(
                id="INV_ORDER_STAYS_COMPLETED",
                name="The completed order is not cancelled",
                predicate=ORDER_COMPLETED,
                source_rule="NXC-CANCEL-ELIGIBLE",
            ),
            WorkflowInvariant(
                id="INV_NO_REFUND",
                name="No refund recorded",
                predicate=NO_REFUND_RECORDED,
                source_rule="NXC-CANCEL-ELIGIBLE",
            ),
        ],
        protected_fields=_protected(
            "orders.latest.status",
            "orders.latest.paymentStatus",
            "payments.latestStatus",
            "refunds.count",
        ),
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_DECLINED",
                type="REJECTION",
                terminal_state_id="ELIGIBILITY_CHECKED",
                description="The agent checked the order and did not cancel it.",
                task_prompt=COMPLETED_CANCEL_TASK,
                predicate=ORDER_COMPLETED,
            ),
            FinalOutcome(
                outcome_id="OUTCOME_REJECTED",
                type="REJECTION",
                terminal_state_id="CANCEL_REJECTED",
                description="NexaCart rejected the cancellation and the order is still COMPLETED.",
                task_prompt=COMPLETED_CANCEL_TASK,
                predicate=ORDER_COMPLETED,
            ),
        ],
        builder_version="c2_handcrafted_nexacart_v1",
        assumptions=[
            "Fixture: one COMPLETED order paid in full (COMPLETED_PAID_ORDER_FIXTURE), no refunds.",
            "Declining after a lookup and a rejected cancellation are both acceptable outcomes.",
        ],
    )


@dataclass(frozen=True)
class NexaCartWorkflow:
    """A NexaCart reference workflow: its EFSM builder and the harness fixture it runs on."""

    model_id: str
    title: str
    kind: str  # "ACCEPTING" or "REJECTION"
    builder: Callable[[str], EFSMModelDefinition]
    fixture_id: str
    fixture_definition: dict
    business_rules: list[str] = field(default_factory=list)


NEXACART_WORKFLOWS: dict[str, NexaCartWorkflow] = {
    w.model_id: w
    for w in (
        NexaCartWorkflow(
            model_id="nxc_cancelled_order_refund",
            title="Refund a cancelled, paid order",
            kind="ACCEPTING",
            builder=build_nexacart_cancelled_order_refund_efsm,
            fixture_id="CANCELLED_PAID_ORDER_FIXTURE",
            fixture_definition=CANCELLED_PAID_ORDER_FIXTURE,
            business_rules=[
                "NXC-REFUND-CANCELLED",
                "NXC-REFUND-PAID",
                "NXC-REFUND-LIMIT",
                "NXC-REFUND-IDEMPOTENT",
            ],
        ),
        NexaCartWorkflow(
            model_id="nxc_cancel_then_refund",
            title="Cancel a paid order, then refund it",
            kind="ACCEPTING",
            builder=build_nexacart_cancel_then_refund_efsm,
            fixture_id="CONFIRMED_PAID_ORDER_FIXTURE",
            fixture_definition=CONFIRMED_PAID_ORDER_FIXTURE,
            business_rules=[
                "NXC-CANCEL-ELIGIBLE",
                "NXC-REFUND-CANCELLED",
                "NXC-REFUND-LIMIT",
            ],
        ),
        NexaCartWorkflow(
            model_id="nxc_pay_pending_order",
            title="Pay a pending order",
            kind="ACCEPTING",
            builder=build_nexacart_pay_pending_order_efsm,
            fixture_id="PENDING_UNPAID_ORDER_FIXTURE",
            fixture_definition=PENDING_UNPAID_ORDER_FIXTURE,
            business_rules=["NXC-PAY-PENDING"],
        ),
        NexaCartWorkflow(
            model_id="nxc_uncancelled_refund_rejection",
            title="Refund request for a non-cancelled order (expected rejection)",
            kind="REJECTION",
            builder=build_nexacart_uncancelled_refund_rejection_efsm,
            fixture_id="CONFIRMED_PAID_ORDER_FIXTURE",
            fixture_definition=CONFIRMED_PAID_ORDER_FIXTURE,
            business_rules=["NXC-REFUND-CANCELLED"],
        ),
        NexaCartWorkflow(
            model_id="nxc_completed_order_cancel_rejection",
            title="Cancel request for a completed order (expected rejection)",
            kind="REJECTION",
            builder=build_nexacart_completed_order_cancel_rejection_efsm,
            fixture_id="COMPLETED_PAID_ORDER_FIXTURE",
            fixture_definition=COMPLETED_PAID_ORDER_FIXTURE,
            business_rules=["NXC-CANCEL-ELIGIBLE"],
        ),
    )
}


def nexacart_workflow_for_model(model_id: str) -> NexaCartWorkflow | None:
    return NEXACART_WORKFLOWS.get(model_id)
