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

IT_HELPDESK_USER_REQUEST = (
    "Device DEV-709 in London Branch is unresponsive. "
    "Check its current diagnostic status and initiate a reboot with reason 'Memory leak threshold exceeded'."
)

IT_HELPDESK_FIXTURE_DATA: dict[str, Any] = {
    "fixture_device_709": {
        "device_id": "DEV-709",
        "hostname": "lon-branch-gw01",
        "status": "UNRESPONSIVE",
        "allowed_reboot": True,
        "location": "London Branch",
    }
}


def get_it_helpdesk_example_config() -> ProjectConfigCreate:
    """Second distinct project configuration representing IT device maintenance and ticket operations.
    Used to verify multi-configuration generator behavior.
    """
    tools = [
        ToolDefinition(
            name="query_device_status",
            description="Queries current operational telemetry and health of a managed device.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "device_id": {
                        "type": "string",
                        "description": "Managed device hardware identifier",
                    }
                },
                required=["device_id"],
            ),
        ),
        ToolDefinition(
            name="reboot_managed_device",
            description="Sends an authorized reboot signal to a remote network device.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "device_id": {"type": "string"},
                    "force": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["device_id", "reason"],
            ),
        ),
        ToolDefinition(
            name="assign_service_ticket",
            description="Assigns an internal support ticket to an on-call engineer.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "ticket_id": {"type": "string"},
                    "assignee_id": {"type": "string"},
                },
                required=["ticket_id", "assignee_id"],
            ),
        ),
    ]

    requirements = [
        TaskRequirement(
            req_id="REQ-DEVICE-001",
            version="1.0",
            title="Authorized Device Reboot",
            description="Reboot actions must specify an active managed device_id and audit reason.",
            category="operational",
        ),
        TaskRequirement(
            req_id="REQ-DEVICE-FLOW",
            version="1.0",
            title="Pre-reboot Telemetry Check",
            description="Agents must inspect device status before issuing reboot commands.",
            category="workflow",
        ),
    ]

    tool_constraints = ToolConstraints(
        permitted_tools=[
            "query_device_status",
            "reboot_managed_device",
            "assign_service_ticket",
        ],
        required_tools=["query_device_status", "reboot_managed_device"],
        forbidden_tools=["factory_reset_device"],
        max_invocations={"reboot_managed_device": 1},
    )

    expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="query_device_status",
                is_required=True,
                min_count=1,
                must_precede_tools=["reboot_managed_device"],
                requirement_refs=["REQ-DEVICE-FLOW"],
            ),
            ToolSelectionExpectation(
                tool_name="reboot_managed_device",
                is_required=True,
                min_count=1,
                max_count=1,
                requirement_refs=["REQ-DEVICE-001"],
            ),
        ],
        argument_constraints={
            "reboot_managed_device": [
                ArgumentConstraint(
                    argument_name="device_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="DEV-709",
                    source_relationship=SourceDataRelationship(
                        source_record_id="fixture_device_709",
                        source_path="device_id",
                        relationship_type=SourceRelationshipType.EXACT_MATCH,
                    ),
                    requirement_refs=["REQ-DEVICE-001"],
                ),
                ArgumentConstraint(
                    argument_name="reason",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.CONTAINS,
                    expected_value="Memory leak",
                    requirement_refs=["REQ-DEVICE-001"],
                ),
            ]
        },
        evidence_requirements=[
            EvidenceRequirement(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                required_for_checks=["reboot_args_check"],
            )
        ],
    )

    return ProjectConfigCreate(
        version=1,
        agent_connection_ref="conn_it_helpdesk_staging",
        tools=tools,
        requirements=requirements,
        tool_constraints=tool_constraints,
        expectations=expectations.model_dump(),
        synthetic_fixture_refs=["synthetic_devices_dataset"],
        reset_capability=ResetCapability(
            capability_ref="restore_device_inventory",
            hook_type="CLI_COMMAND",
            is_idempotent=True,
            details={"seed_profile": "it_branch_devices"},
        ),
        trace_capabilities=[
            TraceCapability(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                description="Device management CLI audit log",
                enabled=True,
            )
        ],
    )
