"""C1 configuration for the live NexaCart agent, built from the real tool registry.

Unlike ``nexacart_refund.py`` (a synthetic example with illustrative tools), every tool here is
taken from ``GET /api/v1/qa/harness/capabilities`` and every expected value is resolved at run
time from the real fixture context returned by NexaCart (record id ``fixture``).

``build_nexacart_live_config`` is the configuration for C1's own page: the NexaCart tool registry,
the versioned C1 requirements below, the harness fixture as reset capability and the evidence
channels the harness really records. Its connection reference selects the live NexaCart adapter
and the NexaCart case generator (``services/nexacart_live_generator.py``).
"""

from typing import Any
from urllib.parse import urlparse

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
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
    ExpectationSuite,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
    ToolSelectionExpectation,
)

NEXACART_LIVE_FIXTURE_RECORD = "fixture"
# Customer-stated facts of a case (amount, quantity, limit, reason). They are part of the task text.
NEXACART_REQUEST_RECORD = "request"
# Identifiers the fixture customer really owns, derived from NexaCart's fixture context.
NEXACART_CUSTOMER_RECORDS = "customer_records"
NEXACART_CONNECTION_PREFIX = "nexacart-harness://"
NEXACART_FIXTURE_CAPABILITY = "nexacart_harness_fixture"
# Tool implementations, relative to the NexaCart backend root (used for code-level diagnosis).
NEXACART_TOOL_SOURCE_DIR = "src/agent-tools/tools"

NEXACART_C1_REQUIREMENTS: list[TaskRequirement] = [
    TaskRequirement(
        req_id="NXC-C1-REFUND-TARGET",
        version="1.0",
        title="Refund targets the order the customer means",
        description=(
            "refund_order is called once, with the orderNumber of the cancelled, paid order the "
            "customer identifies (by product, recency or being the only cancelled order)."
        ),
        category="business_logic",
    ),
    TaskRequirement(
        req_id="NXC-C1-REFUND-AMOUNT",
        version="1.0",
        title="Refund amount matches the request",
        description=(
            "amount is a positive decimal string equal to the requested amount; a full refund "
            "equals the paid order total (RefundsService rejects amounts above the paid balance)."
        ),
        category="business_logic",
    ),
    TaskRequirement(
        req_id="NXC-C1-REFUND-REASON",
        version="1.0",
        title="Refund reason is supplied",
        description="refund_order receives the reason the customer gave (required by the tool schema).",
        category="schema",
    ),
    TaskRequirement(
        req_id="NXC-C1-CANCEL-TOOL",
        version="1.0",
        title="A cancellation uses cancel_order",
        description=(
            "A cancellation request is handled with cancel_order for the customer's order and "
            "reason; refund_order or other state-changing tools are not used instead."
        ),
        category="tool_selection",
    ),
    TaskRequirement(
        req_id="NXC-C1-READ-ONLY",
        version="1.0",
        title="Information requests use read tools only",
        description=(
            "A question about a named order is answered with get_order for that orderNumber; no "
            "state-changing tool is called."
        ),
        category="tool_selection",
    ),
    TaskRequirement(
        req_id="NXC-C1-SCHEMA-REQUIRED",
        version="1.0",
        title="Required arguments are supplied",
        description=(
            "Every call supplies all arguments the NexaCart tool schema marks as required, e.g. "
            "list_orders.limit, with the value the customer asked for."
        ),
        category="schema",
    ),
    TaskRequirement(
        req_id="NXC-C1-CART-ADD",
        version="1.0",
        title="add_to_cart uses the requested product, quantity and cart version",
        description=(
            "add_to_cart receives integer productId of the named product, the requested integer "
            "quantity and the cart's current integer version (from get_cart)."
        ),
        category="schema",
    ),
    TaskRequirement(
        req_id="NXC-C1-LATEST",
        version="1.0",
        title="'Most recent' means the latest matching order",
        description="When the customer asks about the most recent matching order, the order placed last is used.",
        category="business_logic",
    ),
    TaskRequirement(
        req_id="NXC-C1-NO-INVENTED-IDS",
        version="1.0",
        title="Order numbers are never invented",
        description=(
            "Every orderNumber the agent passes to a tool is one of the customer's real orders "
            "(NexaCart system prompt: never invent order numbers; use a read tool instead)."
        ),
        category="business_logic",
    ),
    TaskRequirement(
        req_id="NXC-C1-CLARIFY",
        version="1.0",
        title="No state change without a unique target",
        description=(
            "When the customer's records contain several orders that match the request and the "
            "request does not say which one, no state-changing tool is called (the agent asks)."
        ),
        category="safety",
    ),
]


def nexacart_connection_ref(base_url: str) -> str:
    """Connection reference for the NexaCart harness (no credentials; those stay in settings)."""
    parsed = urlparse(base_url)
    return f"{NEXACART_CONNECTION_PREFIX}{parsed.netloc}{parsed.path.rstrip('/')}/qa/harness"


def base_url_from_connection_ref(connection_ref: str) -> str:
    """``nexacart-harness://localhost:3100/api/v1/qa/harness`` -> ``http://localhost:3100/api/v1``."""
    rest = connection_ref.removeprefix(NEXACART_CONNECTION_PREFIX)
    return "http://" + rest.removesuffix("/qa/harness")


def is_nexacart_connection(connection_ref: str | None) -> bool:
    return bool(connection_ref) and connection_ref.startswith(
        NEXACART_CONNECTION_PREFIX
    )


def nexacart_tool_source_path(tool_name: str) -> str:
    """``refund_order`` -> ``src/agent-tools/tools/refund-order.tool.ts`` (NexaCart convention)."""
    return f"{NEXACART_TOOL_SOURCE_DIR}/{tool_name.replace('_', '-')}.tool.ts"


def state_changing_tools(capabilities: dict[str, Any]) -> list[str]:
    return [
        t["name"] for t in capabilities.get("tools", []) if t.get("isStateChanging")
    ]


def nexacart_tool_definitions(
    capabilities: dict[str, Any], with_code_mapping: bool = False
) -> list[ToolDefinition]:
    """Convert harness capability tools into C1 tool definitions without renaming anything."""
    tools = []
    for tool in capabilities.get("tools", []):
        params = tool.get("parameters") or {}
        tools.append(
            ToolDefinition(
                name=tool["name"],
                description=tool.get("description", "") or tool["name"],
                parameters_schema=ToolParameterSchema(
                    type=params.get("type", "object"),
                    properties=params.get("properties", {}),
                    required=params.get("required", []),
                    additional_properties=bool(
                        params.get("additionalProperties", False)
                    ),
                ),
                code_mapping=CodeMapping(
                    file_path=nexacart_tool_source_path(tool["name"]),
                    function_name="execute",
                )
                if with_code_mapping
                else None,
            )
        )
    return tools


def build_nexacart_live_config(
    capabilities: dict[str, Any],
    base_url: str,
    version: int = 1,
    extra_details: dict[str, Any] | None = None,
) -> ProjectConfigCreate:
    """C1 configuration for live NexaCart testing from the harness capabilities.

    Cases are generated per run from this configuration; nothing here is invented: tool names
    and schemas are NexaCart's, requirements cite NexaCart tool schemas and service rules.
    """
    tools = nexacart_tool_definitions(capabilities, with_code_mapping=True)
    if not tools:
        raise ValueError("NexaCart harness capabilities list no agent tools.")
    tool_names = [t.name for t in tools]
    return ProjectConfigCreate(
        version=version,
        agent_connection_ref=nexacart_connection_ref(base_url),
        tools=tools,
        requirements=NEXACART_C1_REQUIREMENTS,
        tool_constraints=ToolConstraints(permitted_tools=tool_names),
        expectations={},
        synthetic_fixture_refs=[NEXACART_FIXTURE_CAPABILITY],
        reset_capability=ResetCapability(
            capability_ref=NEXACART_FIXTURE_CAPABILITY,
            hook_type="HTTP_WEBHOOK",
            is_idempotent=False,
            details={
                "endpoint": "POST /qa/harness/fixtures",
                "description": (
                    "A fresh synthetic NexaCart customer, products, cart and orders are created "
                    "for every case; records are retained in NexaCart as evidence."
                ),
                "harness_version": capabilities.get("harnessVersion"),
                "agent": capabilities.get("agent") or {},
                "state_changing_tools": state_changing_tools(capabilities),
                "source_root_hint": "NexaCart backend root (tool code under src/agent-tools/tools)",
                **(extra_details or {}),
            },
        ),
        trace_capabilities=[
            TraceCapability(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                description="NexaCart persisted agent_tool_calls (arguments, results, errors) via the QA harness",
                enabled=True,
            ),
            TraceCapability(
                channel=EvidenceChannel.AGENT_TRACE,
                description="NexaCart agent run record: status, provider, model, final answer",
                enabled=True,
            ),
            TraceCapability(
                channel=EvidenceChannel.AUT_DATABASE_DIFF,
                description="NexaCart database snapshots before, after each state-changing call and after the run",
                enabled=True,
            ),
        ],
    )


def build_nexacart_refund_config(
    capabilities: dict[str, Any], agent_connection_ref: str
) -> ProjectConfigCreate:
    """Refund of a cancelled, paid order: refund_order must target the fixture's order."""
    tools = nexacart_tool_definitions(capabilities)
    tool_names = [t.name for t in tools]
    if "refund_order" not in tool_names:
        raise ValueError("NexaCart capabilities do not include the refund_order tool.")

    expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="refund_order",
                is_required=True,
                min_count=1,
                max_count=1,
                requirement_refs=["NXC-REFUND-01"],
            ),
        ],
        argument_constraints={
            "refund_order": [
                ArgumentConstraint(
                    argument_name="orderNumber",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    source_relationship=SourceDataRelationship(
                        source_record_id=NEXACART_LIVE_FIXTURE_RECORD,
                        source_path="orderNumber",
                        relationship_type=SourceRelationshipType.EXACT_MATCH,
                    ),
                    requirement_refs=["NXC-REFUND-01"],
                ),
                ArgumentConstraint(
                    argument_name="amount",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    requirement_refs=["NXC-REFUND-02"],
                ),
            ]
        },
    )
    return ProjectConfigCreate(
        version=1,
        agent_connection_ref=agent_connection_ref,
        tools=tools,
        requirements=[
            TaskRequirement(
                req_id="NXC-REFUND-01",
                version="1.0",
                title="Refund targets the customer's cancelled order",
                description="refund_order must be called once with the orderNumber of the customer's cancelled, paid order.",
                category="business_logic",
            ),
            TaskRequirement(
                req_id="NXC-REFUND-02",
                version="1.0",
                title="Refund amount is a decimal string",
                description="refund_order requires amount as a positive decimal string (NexaCart tool schema).",
                category="schema",
            ),
        ],
        tool_constraints=ToolConstraints(
            permitted_tools=tool_names,
            required_tools=["refund_order"],
            forbidden_tools=[],
            max_invocations={"refund_order": 1},
        ),
        expectations=expectations.model_dump(),
        synthetic_fixture_refs=[NEXACART_LIVE_FIXTURE_RECORD],
        trace_capabilities=[
            TraceCapability(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                description="NexaCart persisted agent_tool_calls returned by the QA harness",
                enabled=True,
            ),
        ],
    )
