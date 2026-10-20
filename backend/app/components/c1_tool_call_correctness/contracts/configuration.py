from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceChannel(str, Enum):
    AGENT_TRACE = "AGENT_TRACE"
    TOOL_CALL_LOG = "TOOL_CALL_LOG"
    AUT_DATABASE_DIFF = "AUT_DATABASE_DIFF"
    HTTP_TRAFFIC = "HTTP_TRAFFIC"
    CONSOLE_OUTPUT = "CONSOLE_OUTPUT"


class CodeMapping(BaseModel):
    """Optional source-code mapping. Source-code access is strictly optional."""

    file_path: str | None = Field(
        default=None, description="Path to repository source file"
    )
    function_name: str | None = Field(
        default=None, description="Target function or method name"
    )
    line_start: int | None = Field(default=None, description="Starting line number")
    line_end: int | None = Field(default=None, description="Ending line number")
    git_ref: str | None = Field(default=None, description="Commit hash, branch, or tag")


class ToolParameterSchema(BaseModel):
    """JSON Schema contract describing tool input arguments."""

    type: str = Field(
        default="object", description="JSON schema root type, usually 'object'"
    )
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Property schemas"
    )
    required: list[str] = Field(
        default_factory=list, description="List of required property names"
    )
    additional_properties: bool = Field(
        default=False, description="Whether extra properties are permitted"
    )


class ToolDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unique tool name")
    description: str = Field(
        ..., min_length=1, description="Functional summary of the tool"
    )
    parameters_schema: ToolParameterSchema = Field(default_factory=ToolParameterSchema)
    code_mapping: CodeMapping | None = Field(
        default=None,
        description="Optional repository code link. Not required for correctness testing.",
    )


class TaskRequirement(BaseModel):
    req_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Stable requirement identifier, e.g. REQ-REFUND-001",
    )
    version: str = Field(
        default="1.0",
        min_length=1,
        max_length=20,
        description="Requirement version tag",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short human-readable requirement title",
    )
    description: str = Field(
        ..., min_length=1, description="Full behavioral requirement statement"
    )
    category: str | None = Field(
        default=None, description="Classification, e.g. business_logic, safety, schema"
    )


class ToolConstraints(BaseModel):
    permitted_tools: list[str] = Field(
        default_factory=list,
        description="Tools the agent is explicitly allowed to invoke",
    )
    required_tools: list[str] = Field(
        default_factory=list,
        description="Tools the agent must invoke to satisfy the task",
    )
    forbidden_tools: list[str] = Field(
        default_factory=list,
        description="Tools the agent must never invoke in this context",
    )
    max_invocations: dict[str, int] = Field(
        default_factory=dict, description="Maximum allowed invocations per tool name"
    )


class ResetCapability(BaseModel):
    capability_ref: str = Field(
        ..., min_length=1, description="Identifier of the environment reset hook"
    )
    hook_type: str = Field(
        default="STATE_RESET",
        description="Reset mechanism, e.g. DB_SNAPSHOT, HTTP_WEBHOOK, CLI",
    )
    is_idempotent: bool = Field(
        default=True, description="Whether repeating the reset is safe and idempotent"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Configuration parameters for the reset hook"
    )


class TraceCapability(BaseModel):
    channel: EvidenceChannel = Field(..., description="Evidence recording channel")
    description: str | None = Field(
        default=None, description="Description of recorded evidence"
    )
    enabled: bool = Field(
        default=True, description="Whether channel is active for this configuration"
    )


# Request & Response Contracts


class ProjectConfigCreate(BaseModel):
    """Payload to create a new Component 1 project configuration version."""

    version: int = Field(
        default=1, ge=1, description="Sequential configuration version number"
    )
    agent_connection_ref: str = Field(
        ...,
        min_length=1,
        description="Stable reference to existing agent connection/credentials. Never contains raw secrets.",
    )
    tools: list[ToolDefinition] = Field(
        default_factory=list,
        description="Tool definitions with schemas and optional code mappings",
    )
    requirements: list[TaskRequirement] = Field(
        default_factory=list, description="Versioned task requirements"
    )
    tool_constraints: ToolConstraints = Field(
        default_factory=ToolConstraints, description="Tool selection rules and limits"
    )
    expectations: dict[str, Any] = Field(
        default_factory=dict,
        description="Declarative expectation suite (ExpectationSuite serialized payload)",
    )
    synthetic_fixture_refs: list[str] = Field(
        default_factory=list,
        description="References to synthetic test fixture datasets or state files",
    )
    reset_capability: ResetCapability | None = Field(
        default=None, description="Environment reset capability reference"
    )
    trace_capabilities: list[TraceCapability] = Field(
        default_factory=list,
        description="Supported and active trace and evidence channels",
    )


class ProjectConfigUpdate(BaseModel):
    """Payload to update an existing, mutable configuration version."""

    agent_connection_ref: str | None = Field(default=None, min_length=1)
    tools: list[ToolDefinition] | None = None
    requirements: list[TaskRequirement] | None = None
    tool_constraints: ToolConstraints | None = None
    expectations: dict[str, Any] | None = None
    synthetic_fixture_refs: list[str] | None = None
    reset_capability: ResetCapability | None = None
    trace_capabilities: list[TraceCapability] | None = None


class ProjectConfigResponse(BaseModel):
    id: str
    project_id: str
    version: int
    is_immutable: bool
    agent_connection_ref: str
    tools: list[ToolDefinition]
    requirements: list[TaskRequirement]
    tool_constraints: ToolConstraints
    expectations: dict[str, Any]
    synthetic_fixture_refs: list[str]
    reset_capability: ResetCapability | None
    trace_capabilities: list[TraceCapability]
    created_at: datetime
    updated_at: datetime
