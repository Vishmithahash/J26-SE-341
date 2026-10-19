import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import InstructionSourceType


class RoleDefinition(BaseModel):
    """Principal role definition within a project domain."""

    model_config = ConfigDict(extra="forbid")

    role_name: str = Field(..., min_length=1, description="Role identifier, e.g. 'CUSTOMER_SUPPORT'")
    description: str = Field(..., description="Description of role responsibilities")
    hierarchy_level: int = Field(default=1, ge=1, description="Hierarchical authorization tier")
    permitted_actions: list[str] = Field(
        default_factory=list, description="Action or tool names explicitly permitted for this role"
    )


class ToolParameterSchema(BaseModel):
    """Schema and bounds for a tool parameter."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Parameter name, e.g. 'amount'")
    param_type: str = Field(
        ..., description="'string', 'integer', 'number', 'boolean', 'object', 'array'"
    )
    unit: str | None = Field(default=None, description="Measurement unit, e.g. 'cents', 'usd', 'days'")
    min_value: float | None = Field(default=None, description="Minimum allowable value if numeric")
    max_value: float | None = Field(default=None, description="Maximum allowable value if numeric")
    required: bool = Field(default=True, description="Whether parameter is required")
    description: str | None = Field(default=None, description="Parameter description")


class ToolDefinition(BaseModel):
    """Tool definition declared by application domain."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1, description="Unique tool name, e.g. 'process_refund'")
    description: str = Field(..., description="Tool description exposed to agent")
    parameters: list[ToolParameterSchema] = Field(
        default_factory=list, description="Declared parameter schemas"
    )
    mutates_state: bool = Field(default=True, description="Whether tool execution commits persistent state change")
    target_resource: str | None = Field(
        default=None, description="Resource type acted upon, e.g. 'order_refund'"
    )


class ResourceDefinition(BaseModel):
    """Resource type and ownership schema."""

    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(..., min_length=1, description="Resource entity name, e.g. 'order_refund'")
    identifier_field: str = Field(..., description="Key identifying resource, e.g. 'order_id'")
    owner_field: str | None = Field(default=None, description="Field indicating owner or customer ID")
    state_fields: list[str] = Field(
        default_factory=list, description="State fields, e.g. ['status', 'amount']"
    )


class SyntheticFixture(BaseModel):
    """Versioned synthetic fixture representing known test facts."""

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1, description="Fixture ID, e.g. 'fix-order-1234'")
    fixture_version: int = Field(default=1, ge=1, description="Immutable fixture version")
    resource_type: str = Field(..., description="Target resource type")
    known_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Known initial facts (e.g. order_id, amount, status, customer_id)",
    )
    description: str | None = Field(default=None, description="Contextual description of fixture")


class ApprovalStateDefinition(BaseModel):
    """Approval status mapping for domain operations."""

    model_config = ConfigDict(extra="forbid")

    approval_status_field: str = Field(default="status", description="Field indicating approval status")
    approver_role_field: str = Field(
        default="approver_role", description="Field indicating approver role"
    )
    valid_statuses: list[str] = Field(
        default_factory=lambda: ["APPROVED", "DENIED", "PENDING", "NONE"],
        description="Supported approval status values",
    )


class ProtectedDataDefinition(BaseModel):
    """Protected information classification and permitted destinations."""

    model_config = ConfigDict(extra="forbid")

    marker: str = Field(..., min_length=1, description="Synthetic canary or secret marker, e.g. 'CANARY-SECRET-99'")
    classification_label: str = Field(..., description="e.g. 'CONFIDENTIAL_PII'")
    permitted_roles: list[str] = Field(
        default_factory=list, description="Roles permitted to view or disclose this marker"
    )
    permitted_recipients: list[str] = Field(
        default_factory=list, description="Allowed destination channels or recipient identifiers"
    )
    description: str | None = Field(default=None, description="Description of protected data item")


class UntrustedSourceDefinition(BaseModel):
    """Declared untrusted source channel and supported injection surface."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, description="Declared source ID, e.g. 'support_ticket_feed'")
    source_type: InstructionSourceType = Field(
        ..., description="Source channel type (e.g. SUPPORT_TICKET, TOOL_RESPONSE)"
    )
    injection_field: str = Field(
        ..., description="Exact field holding untrusted text, e.g. 'body', 'content'"
    )
    default_channel: str = Field(
        default="support_ticket", description="Human-readable channel identifier"
    )
    description: str | None = Field(default=None, description="Description of channel")


class DomainBinding(BaseModel):
    """Project-scoped domain and application bindings."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str = Field(..., min_length=1, description="Stable domain binding ID, e.g. 'domain-ecommerce-refund'")
    project_id: str = Field(..., min_length=1, description="Owning project ID")
    version: int = Field(default=1, ge=1, description="Immutable binding version")
    description: str | None = Field(default=None, description="Binding description")
    roles: list[RoleDefinition] = Field(default_factory=list, description="Domain principal roles")
    tools: list[ToolDefinition] = Field(default_factory=list, description="Declared tools and schemas")
    resources: list[ResourceDefinition] = Field(default_factory=list, description="Resources and ownership")
    fixtures: list[SyntheticFixture] = Field(default_factory=list, description="Synthetic fixture facts")
    approval_states: list[ApprovalStateDefinition] = Field(
        default_factory=list, description="Approval representations"
    )
    protected_data: list[ProtectedDataDefinition] = Field(
        default_factory=list, description="Classified data definitions"
    )
    untrusted_sources: list[UntrustedSourceDefinition] = Field(
        default_factory=list, description="Declared injection surfaces"
    )
    evidence_capabilities: list[str] = Field(
        default_factory=lambda: [
            "action_attempts",
            "tool_executions",
            "authorization_decisions",
            "effects",
            "disclosures",
            "instruction_sources",
            "exposure",
            "argument_provenance",
        ],
        description="Declared evidence capture capabilities",
    )
    content_hash: str = Field(default="", description="SHA-256 canonical hash")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def compute_binding_hash(binding: DomainBinding) -> str:
    """Compute canonical SHA-256 hash of domain binding structure."""
    dump = binding.model_dump(mode="json", exclude={"content_hash", "created_at"})
    canon_json = json.dumps(dump, sort_keys=True)
    return hashlib.sha256(canon_json.encode("utf-8")).hexdigest()
