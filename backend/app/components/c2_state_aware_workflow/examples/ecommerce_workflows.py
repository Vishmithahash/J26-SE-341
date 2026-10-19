"""Additional E-Commerce workflow definitions for C2 domain portability demonstration.

Workflows:
1. Order Cancellation Workflow (cancel order before fulfillment/dispatch)
2. Shipping Address Change Workflow (update address before dispatch)
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

# ---------------------------------------------------------------------------
# 1. ORDER CANCELLATION WORKFLOW
# ---------------------------------------------------------------------------


def get_cancellation_workflow_input() -> WorkflowInputContract:
    """Return normalized workflow input for order cancellation."""
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="c2_domain_portability_project",
        domain="ecommerce",
        workflow_id="order_cancellation_workflow",
        name="Pre-Fulfillment Order Cancellation Workflow",
        version="1.0.0",
        task="Cancel my pending order #701.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_CANCEL_ELIGIBLE",
                name="Fulfillment Status Eligibility",
                description="Orders can only be cancelled if fulfillment_status == 'PENDING_FULFILLMENT' and shipped_at is None.",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_CANCEL_REJECT_SHIPPED",
                name="Shipped Order Rejection",
                description="If an order is already marked SHIPPED or DELIVERED, cancellation must be rejected.",
                category="rejection",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_CANCEL_EFFECT",
                name="Cancellation State Effect",
                description="Successful cancellation sets status to 'CANCELLED' and restocks reserved inventory.",
                category="effect",
                priority=1,
            ),
        ],
        tools=[
            ToolSpecification(
                tool_name="get_order_details",
                description="Retrieve order fulfillment and shipment status.",
                parameters=[
                    ToolParameterSpec(
                        name="order_id",
                        param_type="integer",
                        required=True,
                        description="Order ID to inspect",
                    )
                ],
            ),
            ToolSpecification(
                tool_name="cancel_order",
                description="Cancel order and trigger inventory restock.",
                parameters=[
                    ToolParameterSpec(
                        name="order_id",
                        param_type="integer",
                        required=True,
                        description="Order ID to cancel",
                    ),
                    ToolParameterSpec(
                        name="reason",
                        param_type="string",
                        required=True,
                        description="Customer cancellation reason",
                    ),
                ],
            ),
        ],
        state_mappings=[
            ObservableStateMapping(
                table_name="orders",
                entity_id_field="order_id",
                field_mappings={
                    "status": "status",
                    "fulfillment_status": "fulfillment_status",
                    "shipped_at": "shipped_at",
                },
            )
        ],
        synthetic_fixtures=[
            SyntheticFixtureReference(
                fixture_id="fixture_cancellation_standard",
                description="Order 701 pending fulfillment; Order 702 already shipped.",
                seed=42,
            )
        ],
    )


def get_cancellation_workflow_model() -> EFSMModelDefinition:
    """Return EFSM model for pre-fulfillment order cancellation."""
    return EFSMModelDefinition(
        project_id="c2_domain_portability_project",
        model_id="order_cancellation_workflow",
        version="1.0.0",
        name="Pre-Fulfillment Order Cancellation EFSM",
        description="Cancels orders that are still pending fulfillment.",
        initial_state_id="INIT",
        accepting_state_ids=["CANCELLED"],
        rejection_state_ids=["CANCELLATION_REJECTED"],
        states=[
            StateDefinition(
                id="INIT",
                name="Initial",
                type=StateType.INITIAL,
                description="Initial state before order inspection.",
            ),
            StateDefinition(
                id="ORDER_INSPECTED",
                name="Order Inspected",
                type=StateType.INTERMEDIATE,
                description="Order details inspected and eligibility evaluated.",
            ),
            StateDefinition(
                id="CANCELLED",
                name="Order Cancelled",
                type=StateType.TERMINAL_ACCEPTING,
                description="Order successfully cancelled and inventory restocked.",
            ),
            StateDefinition(
                id="CANCELLATION_REJECTED",
                name="Cancellation Rejected",
                type=StateType.TERMINAL_REJECTION,
                description="Cancellation cleanly rejected because order was already shipped.",
            ),
        ],
        variables=[
            VariableDeclaration(
                name="selected_order_id",
                type="integer",
                initial_value=None,
                description="ID of the order targeted for cancellation.",
            ),
            VariableDeclaration(
                name="fulfillment_status",
                type="string",
                initial_value="UNKNOWN",
                description="Fulfillment status of target order.",
            ),
        ],
        transitions=[
            TransitionDefinition(
                id="T_INSPECT_ORDER",
                source_state="INIT",
                target_state="ORDER_INSPECTED",
                trigger_event="get_order_details",
                guard=None,
                actions=[
                    VariableUpdate(
                        target_var="selected_order_id",
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="arguments.order_id"
                        ),
                    )
                ],
                source_rules=["RULE_CANCEL_ELIGIBLE"],
                description="Inspect order fulfillment status.",
            ),
            TransitionDefinition(
                id="T_EXECUTE_CANCELLATION",
                source_state="ORDER_INSPECTED",
                target_state="CANCELLED",
                trigger_event="cancel_order",
                guard=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                    op=ComparisonOperator.EQUALS,
                    right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
                ),
                actions=[],
                expected_effects=[
                    ComparisonPredicate(
                        left=FieldRef(scope=ScopeEnum.AFTER, path="orders.status"),
                        op=ComparisonOperator.EQUALS,
                        right="CANCELLED",
                    )
                ],
                source_rules=["RULE_CANCEL_EFFECT"],
                description="Execute order cancellation.",
            ),
            TransitionDefinition(
                id="T_REJECT_CANCELLATION",
                source_state="ORDER_INSPECTED",
                target_state="CANCELLATION_REJECTED",
                trigger_event="reject_request",
                guard=None,
                actions=[],
                source_rules=["RULE_CANCEL_REJECT_SHIPPED"],
                description="Cleanly reject cancellation for already shipped order.",
            ),
        ],
        event_mappings=[
            EventMapping(
                event_id="EVT_ORDER_DETAILS",
                tool_name="get_order_details",
                parameter_mappings={"order_id": "order_id"},
            ),
            EventMapping(
                event_id="EVT_CANCEL_ORDER",
                tool_name="cancel_order",
                parameter_mappings={"order_id": "order_id", "reason": "reason"},
            ),
            EventMapping(
                event_id="EVT_REJECT_REQ",
                tool_name="reject_request",
                parameter_mappings={"reason": "reason"},
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="M_ORDER_VERIFIED",
                name="Order Inspected",
                state_id="ORDER_INSPECTED",
            ),
            MilestoneDefinition(
                id="M_FINAL_RESOLUTION",
                name="Order Cancelled",
                state_id="CANCELLED",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_CANCELLED",
                type="ACCEPTING",
                terminal_state_id="CANCELLED",
                description="Order status is CANCELLED in database.",
            ),
            FinalOutcome(
                outcome_id="OUTCOME_REJECTED",
                type="REJECTION",
                terminal_state_id="CANCELLATION_REJECTED",
                description="Order remains unchanged if shipped.",
            ),
        ],
        entity_continuity_rules=[
            EntityContinuityRule(
                id="RULE_CONTINUITY_ORDER",
                entity_type="orders",
                key_field="order_id",
                bound_variable="selected_order_id",
                description="Cancellation call must reference the exact inspected order_id.",
            )
        ],
        protected_fields=[
            ProtectedField(
                entity_type="ecommerce",
                field_path="customer_id",
                description="Customer ownership must never change during cancellation.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# 2. SHIPPING ADDRESS CHANGE WORKFLOW
# ---------------------------------------------------------------------------


def get_address_change_workflow_input() -> WorkflowInputContract:
    """Return normalized workflow input for shipping address change."""
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="c2_domain_portability_project",
        domain="ecommerce",
        workflow_id="address_change_workflow",
        name="Pre-Dispatch Shipping Address Change Workflow",
        version="1.0.0",
        task="Update delivery address for order #801.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_DISPATCH_CHECK",
                name="Pre-Dispatch Requirement",
                description="Address can only be changed before the package is dispatched (dispatched == False).",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_REJECT_DISPATCHED",
                name="Dispatched Order Address Freeze",
                description="If package has already been handed to courier, address update must be rejected.",
                category="rejection",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_ADDRESS_EFFECT",
                name="Address Update Effect",
                description="Database shipping_address record is updated with new street, city, and zip.",
                category="effect",
                priority=1,
            ),
        ],
        tools=[
            ToolSpecification(
                tool_name="get_shipping_status",
                description="Check if package has been dispatched.",
                parameters=[
                    ToolParameterSpec(
                        name="order_id",
                        param_type="integer",
                        required=True,
                        description="Order ID to check",
                    )
                ],
            ),
            ToolSpecification(
                tool_name="update_shipping_address",
                description="Update delivery address for the order.",
                parameters=[
                    ToolParameterSpec(
                        name="order_id",
                        param_type="integer",
                        required=True,
                        description="Order ID",
                    ),
                    ToolParameterSpec(
                        name="new_address",
                        param_type="string",
                        required=True,
                        description="Full new street address",
                    ),
                ],
            ),
        ],
        state_mappings=[
            ObservableStateMapping(
                table_name="deliveries",
                entity_id_field="order_id",
                field_mappings={
                    "dispatched": "dispatched",
                    "delivery_address": "delivery_address",
                },
            )
        ],
        synthetic_fixtures=[
            SyntheticFixtureReference(
                fixture_id="fixture_address_change",
                description="Order 801 not yet dispatched.",
                seed=42,
            )
        ],
    )


def get_address_change_workflow_model() -> EFSMModelDefinition:
    """Return EFSM model for pre-dispatch address change."""
    return EFSMModelDefinition(
        project_id="c2_domain_portability_project",
        model_id="address_change_workflow",
        version="1.0.0",
        name="Pre-Dispatch Address Change EFSM",
        description="Updates shipping address for packages not yet dispatched.",
        initial_state_id="INIT",
        accepting_state_ids=["ADDRESS_UPDATED"],
        rejection_state_ids=["CHANGE_REJECTED"],
        states=[
            StateDefinition(
                id="INIT",
                name="Initial",
                type=StateType.INITIAL,
                description="Initial state before status check.",
            ),
            StateDefinition(
                id="STATUS_CHECKED",
                name="Status Checked",
                type=StateType.INTERMEDIATE,
                description="Dispatch status confirmed.",
            ),
            StateDefinition(
                id="ADDRESS_UPDATED",
                name="Address Updated",
                type=StateType.TERMINAL_ACCEPTING,
                description="Delivery address successfully updated.",
            ),
            StateDefinition(
                id="CHANGE_REJECTED",
                name="Change Rejected",
                type=StateType.TERMINAL_REJECTION,
                description="Change rejected because parcel was already dispatched.",
            ),
        ],
        variables=[
            VariableDeclaration(
                name="selected_order_id",
                type="integer",
                initial_value=None,
                description="Target order ID.",
            ),
        ],
        transitions=[
            TransitionDefinition(
                id="T_CHECK_STATUS",
                source_state="INIT",
                target_state="STATUS_CHECKED",
                trigger_event="get_shipping_status",
                guard=None,
                actions=[
                    VariableUpdate(
                        target_var="selected_order_id",
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="arguments.order_id"
                        ),
                    )
                ],
                source_rules=["RULE_DISPATCH_CHECK"],
                description="Check parcel dispatch status.",
            ),
            TransitionDefinition(
                id="T_UPDATE_ADDRESS",
                source_state="STATUS_CHECKED",
                target_state="ADDRESS_UPDATED",
                trigger_event="update_shipping_address",
                guard=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.order_id"),
                    op=ComparisonOperator.EQUALS,
                    right=FieldRef(scope=ScopeEnum.VARS, path="selected_order_id"),
                ),
                actions=[],
                expected_effects=[
                    ComparisonPredicate(
                        left=FieldRef(
                            scope=ScopeEnum.AFTER, path="deliveries.delivery_address"
                        ),
                        op=ComparisonOperator.EQUALS,
                        right="456 Market St, Suite 200",
                    )
                ],
                source_rules=["RULE_ADDRESS_EFFECT"],
                description="Update delivery address.",
            ),
            TransitionDefinition(
                id="T_REJECT_ADDRESS_CHANGE",
                source_state="STATUS_CHECKED",
                target_state="CHANGE_REJECTED",
                trigger_event="reject_request",
                guard=None,
                actions=[],
                source_rules=["RULE_REJECT_DISPATCHED"],
                description="Cleanly reject address modification for dispatched parcel.",
            ),
        ],
        event_mappings=[
            EventMapping(
                event_id="EVT_SHIPPING_STATUS",
                tool_name="get_shipping_status",
                parameter_mappings={"order_id": "order_id"},
            ),
            EventMapping(
                event_id="EVT_UPDATE_ADDR",
                tool_name="update_shipping_address",
                parameter_mappings={
                    "order_id": "order_id",
                    "new_address": "new_address",
                },
            ),
            EventMapping(
                event_id="EVT_REJECT_REQ",
                tool_name="reject_request",
                parameter_mappings={"reason": "reason"},
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="M_DISPATCH_VERIFIED",
                name="Dispatch Verified",
                state_id="STATUS_CHECKED",
            ),
            MilestoneDefinition(
                id="M_FINAL_ADDRESS",
                name="Address Updated",
                state_id="ADDRESS_UPDATED",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_ADDRESS_UPDATED",
                type="ACCEPTING",
                terminal_state_id="ADDRESS_UPDATED",
                description="Delivery address updated in database.",
            ),
            FinalOutcome(
                outcome_id="OUTCOME_CHANGE_REJECTED",
                type="REJECTION",
                terminal_state_id="CHANGE_REJECTED",
                description="Address change rejected for dispatched package.",
            ),
        ],
        entity_continuity_rules=[
            EntityContinuityRule(
                id="RULE_CONTINUITY_ADDR",
                entity_type="deliveries",
                key_field="order_id",
                bound_variable="selected_order_id",
                description="Address update must reference the verified order_id.",
            )
        ],
    )
