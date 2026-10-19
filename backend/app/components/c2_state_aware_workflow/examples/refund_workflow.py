"""Synthetic refund example workflow implementation for C2.

Scenario: 'Refund my latest paid order.'
Entities:
- Customer 42
- Older paid order 501 (created 2026-10-10T10:00:00Z)
- Later paid order 503 (created 2026-10-15T15:00:00Z) -> TARGET (latest paid)
- Unpaid order 502 (created 2026-10-12T12:00:00Z) -> INELIGIBLE

Demonstrates:
- Latest-order ordering and tie-breaking
- Customer ownership and paid-order eligibility
- Selected-order variable binding
- Entity continuity through refund and verification
- Expected refund and order/payment state effects
- Rejection of an unpaid-order refund
- Protected state remaining unchanged after rejection
- Required milestones and final outcomes
- An explicitly justified alternative path (order line-item detail inspection)
"""

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    EntityContinuityRule,
    EventMapping,
    FinalOutcome,
    MilestoneDefinition,
    ProtectedField,
    StateDefinition,
    StateType,
    TransitionDefinition,
    VariableDeclaration,
    WorkflowInvariant,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    BusinessRule,
    ObservableStateMapping,
    SyntheticFixtureReference,
    ToolParameterSpec,
    ToolSpecification,
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    ScopeEnum,
    VariableUpdate,
    VariableUpdateOp,
)


def get_refund_workflow_input() -> WorkflowInputContract:
    """Return the normalized workflow input for the synthetic refund scenario."""
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="research_project_nexacart",
        domain="ecommerce",
        workflow_id="order_refund_workflow",
        name="Latest Paid Order Refund Workflow",
        version="1.0.0",
        task="Refund my latest paid order.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_OWNERSHIP",
                name="Customer Ownership",
                description="Orders must belong to the requesting customer (customer_id 42).",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_ELIGIBILITY_PAID",
                name="Paid Order Eligibility",
                description="Only orders with payment_status == 'PAID' are eligible for refund.",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_LATEST_ORDER_SELECTION",
                name="Latest Order Selection and Tie-Breaking",
                description="Select the eligible order with the most recent created_at timestamp. Break ties using higher order_id.",
                category="ordering",
                priority=2,
            ),
            BusinessRule(
                rule_id="RULE_REJECT_UNPAID",
                name="Unpaid Order Rejection",
                description="An attempt to refund an unpaid or pending order must be cleanly rejected.",
                category="rejection",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_REFUND_EFFECT",
                name="Refund State Effect",
                description="A successful refund creates a refund record and updates order payment_status to 'REFUNDED'.",
                category="effect",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_PROTECTED_STATE_INVARIANT",
                name="Protected State Unaltered on Rejection",
                description="Rejection must leave order 502 status, order 501 status, and customer balance unaltered.",
                category="invariant",
                priority=1,
            ),
        ],
        tool_specifications=[
            ToolSpecification(
                tool_name="get_customer_orders",
                description="Retrieve customer orders with payment status and placement timestamps.",
                parameters=[
                    ToolParameterSpec(
                        name="customer_id", type="integer", required=True
                    ),
                ],
                return_type="list",
                has_side_effects=False,
            ),
            ToolSpecification(
                tool_name="get_order_details",
                description="Inspect detailed line items and pricing for a specific order.",
                parameters=[
                    ToolParameterSpec(name="order_id", type="integer", required=True),
                ],
                return_type="dict",
                has_side_effects=False,
            ),
            ToolSpecification(
                tool_name="request_refund",
                description="Submit a refund request for an eligible order.",
                parameters=[
                    ToolParameterSpec(name="order_id", type="integer", required=True),
                    ToolParameterSpec(
                        name="reason",
                        type="string",
                        required=False,
                        default="customer_request",
                    ),
                ],
                return_type="dict",
                has_side_effects=True,
            ),
            ToolSpecification(
                tool_name="verify_refund_status",
                description="Verify that the refund transaction completed and database state updated.",
                parameters=[
                    ToolParameterSpec(name="order_id", type="integer", required=True),
                ],
                return_type="dict",
                has_side_effects=False,
            ),
        ],
        observable_state_mappings=[
            ObservableStateMapping(
                entity_type="orders",
                primary_key="id",
                observable_fields=[
                    "id",
                    "customer_id",
                    "payment_status",
                    "amount",
                    "created_at",
                ],
            ),
            ObservableStateMapping(
                entity_type="refunds",
                primary_key="id",
                observable_fields=["id", "order_id", "amount", "status"],
            ),
        ],
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="fixture_customer_42_refund",
            description="Fictional customer 42 with orders 501 (paid older), 502 (unpaid), and 503 (paid latest).",
            initial_entities={
                "customer": {"id": 42, "name": "Alice Smith", "balance": 0.0},
                "orders": {
                    "501": {
                        "id": 501,
                        "customer_id": 42,
                        "payment_status": "PAID",
                        "amount": 55.0,
                        "created_at": "2026-10-10T10:00:00Z",
                    },
                    "502": {
                        "id": 502,
                        "customer_id": 42,
                        "payment_status": "UNPAID",
                        "amount": 120.0,
                        "created_at": "2026-10-12T12:00:00Z",
                    },
                    "503": {
                        "id": 503,
                        "customer_id": 42,
                        "payment_status": "PAID",
                        "amount": 85.5,
                        "created_at": "2026-10-15T15:00:00Z",
                    },
                },
            },
            protected_state={
                "order_502_payment_status": "UNPAID",
                "customer_42_balance": 0.0,
            },
        ),
        assumptions=[
            "Synthetic timestamps are ISO8601 strings.",
            "Abstract tool names represent simulated e-commerce operations without direct external API coupling.",
        ],
    )


def build_synthetic_refund_efsm() -> EFSMModelDefinition:
    """Build the complete validated EFSM for the 'Refund my latest paid order' workflow."""
    states = [
        StateDefinition(
            id="START",
            name="Workflow Initial State",
            type=StateType.INITIAL,
            description="Agent has received the user request to refund the latest paid order.",
        ),
        StateDefinition(
            id="PAID_ORDERS_RETRIEVED",
            name="Paid Orders Retrieved",
            type=StateType.INTERMEDIATE,
            description="Customer orders have been retrieved via get_customer_orders.",
            milestone="PAID_ORDERS_RETRIEVED",
        ),
        StateDefinition(
            id="LATEST_ELIGIBLE_IDENTIFIED",
            name="Latest Eligible Order Identified",
            type=StateType.INTERMEDIATE,
            description="Order 503 has been selected as the latest paid order (filtering out unpaid 502 and older 501).",
            milestone="LATEST_ELIGIBLE_IDENTIFIED",
        ),
        StateDefinition(
            id="ORDER_DETAILS_INSPECTED",
            name="Order Details Inspected",
            type=StateType.INTERMEDIATE,
            description="Alternative path: Agent verified detailed line items of order 503 prior to refund submission.",
            milestone="ORDER_DETAILS_INSPECTED",
        ),
        StateDefinition(
            id="REFUND_REQUESTED",
            name="Refund Requested",
            type=StateType.INTERMEDIATE,
            description="Refund request tool called for the bound order.",
            milestone="REFUND_REQUESTED",
        ),
        StateDefinition(
            id="REFUNDED",
            name="Order Refunded and Verified",
            type=StateType.TERMINAL_ACCEPTING,
            description="Refund verified in database; order payment_status is REFUNDED.",
            milestone="REFUND_VERIFIED",
        ),
        StateDefinition(
            id="REJECTED_UNPAID",
            name="Unpaid Order Refund Rejected",
            type=StateType.TERMINAL_REJECTION,
            description="Rejection path: Agent or system correctly rejected an attempt to refund unpaid order 502.",
        ),
    ]

    variables = [
        VariableDeclaration(
            name="requesting_customer_id",
            type="integer",
            domain=[42],
            initial_value=42,
            description="Customer making the refund request",
        ),
        VariableDeclaration(
            name="selected_order_id",
            type="integer",
            domain=[501, 502, 503],
            initial_value=None,
            description="The order identified for refund",
        ),
        VariableDeclaration(
            name="target_latest_order_id",
            type="integer",
            domain=[503],
            initial_value=503,
            description="The ground-truth latest paid order ID",
        ),
    ]

    transitions = [
        # 1. Start -> Paid Orders Retrieved
        TransitionDefinition(
            id="T_RETRIEVE_ORDERS",
            source_state="START",
            target_state="PAID_ORDERS_RETRIEVED",
            trigger_event="get_customer_orders",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.customer_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="requesting_customer_id"),
            ),
            actions=[],
            source_rules=["RULE_OWNERSHIP"],
            description="Agent queries orders for customer 42",
        ),
        # 2. Paid Orders Retrieved -> Latest Eligible Order Identified
        TransitionDefinition(
            id="T_SELECT_LATEST_PAID_ORDER",
            source_state="PAID_ORDERS_RETRIEVED",
            target_state="LATEST_ELIGIBLE_IDENTIFIED",
            trigger_event="select_order",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="target_latest_order_id"),
            ),
            actions=[
                VariableUpdate(
                    target_var="selected_order_id",
                    op=VariableUpdateOp.SET,
                    source_ref=FieldRef(
                        scope=ScopeEnum.EVENT, path="arguments.order_id"
                    ),
                )
            ],
            source_rules=["RULE_ELIGIBILITY_PAID", "RULE_LATEST_ORDER_SELECTION"],
            description="Order 503 identified as latest paid order and bound to selected_order_id",
        ),
        # 3. Alternative Path: Inspect order line items before requesting refund
        TransitionDefinition(
            id="T_INSPECT_ORDER_DETAILS",
            source_state="LATEST_ELIGIBLE_IDENTIFIED",
            target_state="ORDER_DETAILS_INSPECTED",
            trigger_event="get_order_details",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
            ),
            actions=[],
            source_rules=["RULE_OWNERSHIP"],
            description="Legitimate alternative path: inspect order details before requesting refund",
        ),
        # 4. Standard Direct Path: Latest Identified -> Refund Requested
        TransitionDefinition(
            id="T_DIRECT_REQUEST_REFUND",
            source_state="LATEST_ELIGIBLE_IDENTIFIED",
            target_state="REFUND_REQUESTED",
            trigger_event="request_refund",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
            ),
            actions=[],
            source_rules=["RULE_ELIGIBILITY_PAID"],
            description="Direct refund request from identified order",
        ),
        # 5. Alternative Path Continuation: Inspected -> Refund Requested
        TransitionDefinition(
            id="T_INSPECTED_REQUEST_REFUND",
            source_state="ORDER_DETAILS_INSPECTED",
            target_state="REFUND_REQUESTED",
            trigger_event="request_refund",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
            ),
            actions=[],
            source_rules=["RULE_ELIGIBILITY_PAID"],
            description="Refund request following order details inspection",
        ),
        # 6. Refund Requested -> Refunded (Accepting outcome)
        TransitionDefinition(
            id="T_VERIFY_REFUND",
            source_state="REFUND_REQUESTED",
            target_state="REFUNDED",
            trigger_event="verify_refund_status",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
            ),
            actions=[],
            expected_effects=[
                ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.AFTER, path="payment_status"),
                    op=ComparisonOperator.EQUALS,
                    right="REFUNDED",
                )
            ],
            source_rules=["RULE_REFUND_EFFECT"],
            description="Verification that payment_status transitioned to REFUNDED",
        ),
        # 7. Rejection Path: Paid Orders Retrieved -> Rejected (Unpaid order 502)
        TransitionDefinition(
            id="T_REJECT_UNPAID_ORDER",
            source_state="PAID_ORDERS_RETRIEVED",
            target_state="REJECTED_UNPAID",
            trigger_event="reject_unpaid_order",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=502,
            ),
            actions=[],
            expected_effects=[
                ComparisonPredicate(
                    left=FieldRef(
                        scope=ScopeEnum.AFTER, path="order_502_payment_status"
                    ),
                    op=ComparisonOperator.EQUALS,
                    right="UNPAID",
                )
            ],
            source_rules=["RULE_REJECT_UNPAID", "RULE_PROTECTED_STATE_INVARIANT"],
            description="Unpaid order 502 refund request cleanly rejected",
        ),
    ]

    event_mappings = [
        EventMapping(
            event_id="EVT_GET_ORDERS",
            tool_name="get_customer_orders",
            parameter_mappings={"customer_id": "customer_id"},
        ),
        EventMapping(
            event_id="EVT_SELECT_ORDER",
            tool_name="select_order",
            parameter_mappings={"order_id": "order_id"},
        ),
        EventMapping(
            event_id="EVT_ORDER_DETAILS",
            tool_name="get_order_details",
            parameter_mappings={"order_id": "order_id"},
        ),
        EventMapping(
            event_id="EVT_REQUEST_REFUND",
            tool_name="request_refund",
            parameter_mappings={"order_id": "order_id"},
        ),
        EventMapping(
            event_id="EVT_VERIFY_REFUND",
            tool_name="verify_refund_status",
            parameter_mappings={"order_id": "order_id"},
        ),
        EventMapping(
            event_id="EVT_REJECT_UNPAID",
            tool_name="reject_unpaid_order",
            parameter_mappings={"order_id": "order_id"},
        ),
    ]

    invariants = [
        WorkflowInvariant(
            id="INV_NEVER_REFUND_UNPAID",
            name="Unpaid Order Cannot Be Refunded",
            predicate=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.AFTER, path="order_502_payment_status"),
                op=ComparisonOperator.NOT_EQUALS,
                right="REFUNDED",
            ),
            description="Order 502 is unpaid and must never be set to REFUNDED under any transition.",
            source_rule="RULE_REJECT_UNPAID",
        )
    ]

    milestones = [
        MilestoneDefinition(
            id="M_RETRIEVED",
            name="Paid Orders Retrieved",
            state_id="PAID_ORDERS_RETRIEVED",
        ),
        MilestoneDefinition(
            id="M_IDENTIFIED",
            name="Latest Eligible Order Identified",
            state_id="LATEST_ELIGIBLE_IDENTIFIED",
        ),
        MilestoneDefinition(
            id="M_REQUESTED", name="Refund Requested", state_id="REFUND_REQUESTED"
        ),
        MilestoneDefinition(
            id="M_REFUNDED", name="Refund Verified", state_id="REFUNDED"
        ),
    ]

    entity_continuity_rules = [
        EntityContinuityRule(
            id="EC_ORDER_CONTINUITY",
            entity_type="orders",
            key_field="id",
            bound_variable="selected_order_id",
            description="The selected order 503 must remain consistent across refund request and verification.",
        )
    ]

    protected_fields = [
        ProtectedField(
            entity_type="ecommerce",
            field_path="order_502_payment_status",
            allowed_mutations=[],
            strict_unchanged_on_rejection=True,
            description="Unpaid order 502 payment status must not change.",
        ),
        ProtectedField(
            entity_type="ecommerce",
            field_path="customer_42_balance",
            allowed_mutations=[],
            strict_unchanged_on_rejection=True,
            description="Customer 42 balance must remain unchanged on rejection.",
        ),
    ]

    final_outcomes = [
        FinalOutcome(
            outcome_id="OUTCOME_REFUND_SUCCESS",
            type="ACCEPTING",
            terminal_state_id="REFUNDED",
            description="Order 503 successfully refunded and verified.",
            task_prompt="Refund my latest paid order.",
            predicate=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.AFTER, path="payment_status"),
                op=ComparisonOperator.EQUALS,
                right="REFUNDED",
            ),
        ),
        FinalOutcome(
            outcome_id="OUTCOME_UNPAID_REJECTED",
            type="REJECTION",
            terminal_state_id="REJECTED_UNPAID",
            description="Ineligible unpaid order 502 rejected; protected state maintained.",
            task_prompt="Refund unpaid order 502.",
            predicate=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.AFTER, path="order_502_payment_status"),
                op=ComparisonOperator.EQUALS,
                right="UNPAID",
            ),
        ),
    ]

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id="research_project_nexacart",
        model_id="refund_efsm",
        version="1.0.0",
        name="Latest Paid Order Refund EFSM",
        description="EFSM for refunding customer 42's latest paid order (503).",
        states=states,
        initial_state_id="START",
        accepting_state_ids=["REFUNDED"],
        rejection_state_ids=["REJECTED_UNPAID"],
        variables=variables,
        transitions=transitions,
        event_mappings=event_mappings,
        invariants=invariants,
        milestones=milestones,
        entity_continuity_rules=entity_continuity_rules,
        protected_fields=protected_fields,
        final_outcomes=final_outcomes,
        builder_version="c2_handcrafted_reference_v1",
        assumptions=[
            "Customer 42 has orders 501 (paid), 502 (unpaid), and 503 (paid).",
            "Order 503 is strictly newer than order 501.",
            "Alternative path allows inspecting line item details before submitting refund.",
        ],
        diagnostics=["Reference model verified against Appendix A and D of proposal."],
    )


def get_unpaid_order_workflow_input() -> WorkflowInputContract:
    """Return the workflow input specifically for the 'Refund unpaid order 502' rejection task."""
    base_input = get_refund_workflow_input()
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="research_project_nexacart",
        domain="ecommerce",
        workflow_id="order_502_unpaid_rejection_workflow",
        name="Unpaid Order 502 Rejection Workflow",
        version="1.0.0",
        task="Refund unpaid order 502.",
        business_rules=base_input.business_rules,
        tool_specifications=base_input.tool_specifications,
        observable_state_mappings=base_input.observable_state_mappings,
        synthetic_fixture=base_input.synthetic_fixture,
        assumptions=[
            "Order 502 is explicitly unpaid and cannot be refunded.",
            "Rejection must preserve protected fields.",
        ],
    )


def build_synthetic_unpaid_order_rejection_efsm() -> EFSMModelDefinition:
    """Build dedicated EFSM where the specific task is to refund unpaid order 502, requiring clean rejection."""
    states = [
        StateDefinition(
            id="START",
            name="Workflow Initial State",
            type=StateType.INITIAL,
            description="Agent has received the user request to refund unpaid order 502.",
        ),
        StateDefinition(
            id="PAID_ORDERS_RETRIEVED",
            name="Customer Orders Retrieved",
            type=StateType.INTERMEDIATE,
            description="Orders retrieved to inspect order status.",
            milestone="PAID_ORDERS_RETRIEVED",
        ),
        StateDefinition(
            id="REJECTED_UNPAID",
            name="Unpaid Order Refund Rejected",
            type=StateType.TERMINAL_REJECTION,
            description="Agent cleanly rejected the request to refund unpaid order 502 without state mutation.",
            milestone="REJECTION_COMPLETED",
        ),
    ]

    variables = [
        VariableDeclaration(
            name="requesting_customer_id",
            type="integer",
            domain=[42],
            initial_value=42,
        ),
        VariableDeclaration(
            name="target_order_id",
            type="integer",
            domain=[502],
            initial_value=502,
        ),
    ]

    transitions = [
        TransitionDefinition(
            id="T_RETRIEVE_ORDERS_FOR_REJECTION",
            source_state="START",
            target_state="PAID_ORDERS_RETRIEVED",
            trigger_event="get_customer_orders",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.customer_id"),
                op=ComparisonOperator.EQUALS,
                right=FieldRef(scope=ScopeEnum.VARS, path="requesting_customer_id"),
            ),
            actions=[],
            source_rules=["RULE_OWNERSHIP"],
            description="Retrieve orders for customer 42",
        ),
        TransitionDefinition(
            id="T_REJECT_UNPAID_ORDER_502",
            source_state="PAID_ORDERS_RETRIEVED",
            target_state="REJECTED_UNPAID",
            trigger_event="reject_unpaid_order",
            guard=ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                op=ComparisonOperator.EQUALS,
                right=502,
            ),
            actions=[],
            expected_effects=[
                ComparisonPredicate(
                    left=FieldRef(
                        scope=ScopeEnum.AFTER, path="order_502_payment_status"
                    ),
                    op=ComparisonOperator.EQUALS,
                    right="UNPAID",
                )
            ],
            source_rules=["RULE_REJECT_UNPAID", "RULE_PROTECTED_STATE_INVARIANT"],
            description="Clean rejection of unpaid order 502",
        ),
    ]

    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id="research_project_nexacart",
        model_id="unpaid_refund_rejection_efsm",
        version="1.0.0",
        name="Unpaid Order Rejection EFSM",
        description="Dedicated EFSM for handling refund requests for unpaid order 502.",
        states=states,
        initial_state_id="START",
        accepting_state_ids=["REJECTED_UNPAID"],  # Accepting or rejection terminal
        rejection_state_ids=["REJECTED_UNPAID"],
        variables=variables,
        transitions=transitions,
        event_mappings=[
            EventMapping(
                event_id="EVT_GET_ORDERS",
                tool_name="get_customer_orders",
                parameter_mappings={"customer_id": "customer_id"},
            ),
            EventMapping(
                event_id="EVT_REJECT_UNPAID",
                tool_name="reject_unpaid_order",
                parameter_mappings={"order_id": "order_id"},
            ),
        ],
        invariants=[
            WorkflowInvariant(
                id="INV_ORDER_502_UNPAID",
                name="Order 502 Remains Unpaid",
                predicate=ComparisonPredicate(
                    left=FieldRef(
                        scope=ScopeEnum.AFTER, path="order_502_payment_status"
                    ),
                    op=ComparisonOperator.EQUALS,
                    right="UNPAID",
                ),
                description="Order 502 status must never transition away from UNPAID.",
                source_rule="RULE_PROTECTED_STATE_INVARIANT",
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="MS_ORDERS_RETRIEVED",
                name="Orders Retrieved",
                state_id="PAID_ORDERS_RETRIEVED",
            ),
            MilestoneDefinition(
                id="MS_REJECTION_COMPLETED",
                name="Rejection Completed",
                state_id="REJECTED_UNPAID",
            ),
        ],
        entity_continuity_rules=[],
        protected_fields=[
            ProtectedField(
                entity_type="orders",
                field_path="order_502_payment_status",
                allowed_mutations=[],
                strict_unchanged_on_rejection=True,
                description="Status of order 502 must remain UNPAID.",
            ),
            ProtectedField(
                entity_type="customers",
                field_path="customer_42_balance",
                allowed_mutations=[],
                strict_unchanged_on_rejection=True,
                description="Customer 42 balance must remain unchanged on rejection.",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_UNPAID_502_REJECTED",
                type="REJECTION",
                terminal_state_id="REJECTED_UNPAID",
                description="Unpaid order 502 cleanly rejected without modifying state.",
                task_prompt="Refund unpaid order 502.",
                predicate=ComparisonPredicate(
                    left=FieldRef(
                        scope=ScopeEnum.AFTER, path="order_502_payment_status"
                    ),
                    op=ComparisonOperator.EQUALS,
                    right="UNPAID",
                ),
            ),
        ],
        builder_version="c2_handcrafted_reference_v1",
        assumptions=[
            "Customer 42 explicitly requested refund for order 502.",
            "Order 502 is unpaid.",
        ],
        diagnostics=["Dedicated negative test scenario."],
    )
