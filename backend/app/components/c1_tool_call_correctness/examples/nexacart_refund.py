from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
    ProjectConfigCreate,
    ResetCapability,
    TaskRequirement,
    ToolConstraints,
    ToolDefinition,
    ToolParameterSchema,
    TraceCapability,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    EvidenceRequirement,
    ExpectationSuite,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
    ToolSelectionExpectation,
)

# Realistic user prompt driving this test case
NEXACART_USER_REQUEST = (
    "Customer requested a refund for item #ITEM-44 in order #ORD-9821 because it arrived damaged. "
    "Verify the order line items and issue the refund in the amount of $35.00."
)

# Simulated synthetic fixture dataset
NEXACART_FIXTURE_DATA: dict[str, Any] = {
    "fixture_order_9821": {
        "order_id": "ORD-9821",
        "customer_id": "CUST-8831",
        "status": "DELIVERED",
        "items": {
            "ITEM-44": {
                "name": "Wireless Ergonomic Mouse",
                "price": 35.00,
                "refundable": True,
            }
        },
    }
}


def get_nexacart_refund_example_config() -> ProjectConfigCreate:
    """Returns a synthetic, production-grade example configuration for the NexaCart refund scenario.
    Demonstrates project input layer, requirement traceability, tool schemas, and source data relationships.
    """
    tools = [
        ToolDefinition(
            name="get_order_details",
            description="Retrieves order metadata, line items, and fulfillment status by order ID.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "order_id": {
                        "type": "string",
                        "description": "Unique order identifier, e.g. ORD-9821",
                    }
                },
                required=["order_id"],
            ),
        ),
        ToolDefinition(
            name="process_refund",
            description="Processes a payment refund for a specific line item in an order.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "order_id": {"type": "string"},
                    "line_item_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "reason": {"type": "string"},
                },
                required=["order_id", "line_item_id", "amount", "reason"],
            ),
        ),
        ToolDefinition(
            name="send_customer_notification",
            description="Dispatches an email or SMS notification to the customer.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "customer_id": {"type": "string"},
                    "message": {"type": "string"},
                },
                required=["customer_id", "message"],
            ),
        ),
    ]

    requirements = [
        TaskRequirement(
            req_id="REQ-REFUND-001",
            version="1.0",
            title="Refund Amount Verification",
            description="The refund amount passed to process_refund must match the recorded item price in the order fixture.",
            category="business_logic",
        ),
        TaskRequirement(
            req_id="REQ-REFUND-002",
            version="1.0",
            title="Mandatory Refund Arguments",
            description="Refund calls must provide non-null order_id, line_item_id, amount, and reason.",
            category="schema",
        ),
        TaskRequirement(
            req_id="REQ-TOOL-FLOW-01",
            version="1.0",
            title="Prior Order Verification",
            description="The agent must invoke get_order_details before invoking process_refund.",
            category="workflow",
        ),
        TaskRequirement(
            req_id="REQ-SAFETY-01",
            version="1.0",
            title="Prohibited Operations",
            description="Destructive database operations and unauthorized credentials modification are strictly prohibited.",
            category="safety",
        ),
    ]

    tool_constraints = ToolConstraints(
        permitted_tools=[
            "get_order_details",
            "process_refund",
            "send_customer_notification",
        ],
        required_tools=["get_order_details", "process_refund"],
        forbidden_tools=["admin_wipe_database"],
        max_invocations={"process_refund": 1},
    )

    expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="get_order_details",
                is_required=True,
                min_count=1,
                must_precede_tools=["process_refund"],
                requirement_refs=["REQ-TOOL-FLOW-01"],
            ),
            ToolSelectionExpectation(
                tool_name="process_refund",
                is_required=True,
                min_count=1,
                max_count=1,
                requirement_refs=["REQ-REFUND-001", "REQ-REFUND-002"],
            ),
        ],
        argument_constraints={
            "process_refund": [
                ArgumentConstraint(
                    argument_name="order_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="ORD-9821",
                    source_relationship=SourceDataRelationship(
                        source_record_id="fixture_order_9821",
                        source_path="order_id",
                        relationship_type=SourceRelationshipType.EXACT_MATCH,
                    ),
                    requirement_refs=["REQ-REFUND-002"],
                ),
                ArgumentConstraint(
                    argument_name="line_item_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="ITEM-44",
                    requirement_refs=["REQ-REFUND-002"],
                ),
                ArgumentConstraint(
                    argument_name="amount",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="number",
                    operator=ComparisonOperator.EQUALS,
                    expected_value=35.00,
                    source_relationship=SourceDataRelationship(
                        source_record_id="fixture_order_9821",
                        source_path="items.ITEM-44.price",
                        relationship_type=SourceRelationshipType.NUMERIC_TOLERANCE,
                        tolerance=0.01,
                    ),
                    requirement_refs=["REQ-REFUND-001"],
                ),
                ArgumentConstraint(
                    argument_name="reason",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.CONTAINS,
                    expected_value="damage",
                    requirement_refs=["REQ-REFUND-002"],
                ),
            ]
        },
        evidence_requirements=[
            EvidenceRequirement(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                required_for_checks=["process_refund_args", "tool_selection_order"],
                description="Raw tool invocation payload and timestamp log",
            ),
            EvidenceRequirement(
                channel=EvidenceChannel.AGENT_TRACE,
                required_for_checks=["tool_selection_order"],
                description="Agent reasoning trace for tool invocation sequence",
            ),
        ],
    )

    return ProjectConfigCreate(
        version=1,
        agent_connection_ref="conn_nexacart_staging_agent",
        tools=tools,
        requirements=requirements,
        tool_constraints=tool_constraints,
        expectations=expectations.model_dump(),
        synthetic_fixture_refs=["fixture_order_9821"],
        reset_capability=ResetCapability(
            capability_ref="nexacart_test_db_restore",
            hook_type="DB_SNAPSHOT_RESTORE",
            is_idempotent=True,
            details={"snapshot_id": "seed_orders_v1"},
        ),
        trace_capabilities=[
            TraceCapability(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                description="NexaCart agent tool invocation logger",
                enabled=True,
            ),
            TraceCapability(
                channel=EvidenceChannel.AGENT_TRACE,
                description="Agent thought and step trace collector",
                enabled=True,
            ),
        ],
    )
