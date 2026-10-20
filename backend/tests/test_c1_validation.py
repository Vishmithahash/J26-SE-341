from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
    TaskRequirement,
    ToolDefinition,
    ToolParameterSchema,
    TraceCapability,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ExpectationSuite,
    FieldPresence,
    SourceDataRelationship,
    ToolSelectionExpectation,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationSeverity,
)
from app.components.c1_tool_call_correctness.examples.nexacart_refund import (
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.services.validator import (
    validate_project_config,
)


def test_valid_nexacart_example_config_passes_validation():
    """Verify that the production-grade synthetic NexaCart example passes semantic validation."""
    config = get_nexacart_refund_example_config()
    summary = validate_project_config(config)

    assert summary.is_valid is True
    assert summary.error_count == 0
    assert not any(i.severity == ValidationSeverity.ERROR for i in summary.issues)


def test_validation_detects_raw_secret_leak():
    """Verify that raw API key tokens in agent_connection_ref are rejected."""
    config = get_nexacart_refund_example_config()
    config.agent_connection_ref = "sk-live-secretkey12345678901234567890"

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_RAW_SECRET_EXPOSED" for i in summary.issues)


def test_validation_detects_empty_connection_ref():
    config = get_nexacart_refund_example_config()
    config.agent_connection_ref = "   "

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_EMPTY_CONNECTION_REF" for i in summary.issues)


def test_validation_detects_duplicate_tool_names():
    config = get_nexacart_refund_example_config()
    config.tools.append(
        ToolDefinition(
            name="get_order_details",  # Duplicate of existing tool
            description="Second duplicate tool",
            parameters_schema=ToolParameterSchema(),
        )
    )

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_DUPLICATE_TOOL_NAME" for i in summary.issues)


def test_validation_detects_duplicate_requirement_ids():
    config = get_nexacart_refund_example_config()
    config.requirements.append(
        TaskRequirement(
            req_id="REQ-REFUND-001",  # Duplicate of existing requirement
            title="Duplicate Refund Rule",
            description="Duplicate description",
        )
    )

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_DUPLICATE_REQ_ID" for i in summary.issues)


def test_validation_detects_unknown_tool_in_constraints():
    config = get_nexacart_refund_example_config()
    config.tool_constraints.required_tools.append("non_existent_tool_xyz")

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(
        i.code == "ERR_UNKNOWN_TOOL_REF" and "non_existent_tool_xyz" in i.message
        for i in summary.issues
    )


def test_validation_detects_tool_constraint_conflict():
    config = get_nexacart_refund_example_config()
    # Tool cannot be both required and forbidden
    config.tool_constraints.required_tools.append("disputed_tool")
    config.tool_constraints.forbidden_tools.append("disputed_tool")
    config.tools.append(
        ToolDefinition(
            name="disputed_tool",
            description="Tool with contradictory constraints",
            parameters_schema=ToolParameterSchema(),
        )
    )

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_TOOL_CONSTRAINT_CONFLICT" for i in summary.issues)


def test_validation_detects_cyclic_tool_precedence():
    """Verify that cycles in tool precedence declarations (A precedes B, B precedes A) are caught."""
    config = get_nexacart_refund_example_config()
    config.expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="get_order_details",
                must_precede_tools=["process_refund"],
            ),
            ToolSelectionExpectation(
                tool_name="process_refund",
                must_precede_tools=["get_order_details"],  # Creates cycle!
            ),
        ]
    ).model_dump()

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_CYCLIC_TOOL_PRECEDENCE" for i in summary.issues)


def test_validation_detects_unknown_requirement_ref_in_expectations():
    config = get_nexacart_refund_example_config()
    config.expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="get_order_details",
                requirement_refs=["REQ-NONEXISTENT-999"],
            )
        ]
    ).model_dump()

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(
        i.code == "ERR_UNKNOWN_REQ_REF" and "REQ-NONEXISTENT-999" in i.message
        for i in summary.issues
    )


def test_validation_detects_invalid_source_relationship():
    config = get_nexacart_refund_example_config()
    config.expectations = ExpectationSuite(
        argument_constraints={
            "process_refund": [
                ArgumentConstraint(
                    argument_name="order_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    source_relationship=SourceDataRelationship(
                        source_record_id="",  # Empty invalid source_record_id
                        source_path="order_id",
                    ),
                )
            ]
        }
    ).model_dump()

    summary = validate_project_config(config)
    assert summary.is_valid is False
    assert any(i.code == "ERR_INVALID_SOURCE_RELATIONSHIP" for i in summary.issues)


def test_validation_warns_on_no_active_trace_channels():
    config = get_nexacart_refund_example_config()
    config.trace_capabilities = [
        TraceCapability(channel=EvidenceChannel.TOOL_CALL_LOG, enabled=False)
    ]

    summary = validate_project_config(config)
    assert summary.is_valid is True  # Warning does not invalidate
    assert any(i.code == "WARN_NO_ACTIVE_TRACE_CHANNEL" for i in summary.issues)
