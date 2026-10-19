from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import (
    EvidenceOrigin,
    ExposureStatus,
    InstructionSourceType,
    TrustClassification,
)


class PrincipalEvidence(BaseModel):
    """Authenticated principal and active role metadata."""

    model_config = ConfigDict(extra="forbid")

    principal_id: str = Field(..., description="Authenticated user or service identity")
    roles: list[str] = Field(
        default_factory=list, description="Roles granted to the principal"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Session and organizational attributes"
    )


class InstructionSourceEvidence(BaseModel):
    """Provenance and authority classification of an instruction source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        ..., description="Unique identifier for the instruction source"
    )
    source_type: InstructionSourceType = Field(
        ..., description="Type of source channel"
    )
    trust_classification: TrustClassification = Field(
        ..., description="Authoritative trust classification"
    )
    origin: EvidenceOrigin = Field(
        default=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE,
        description="Origin of this evidence",
    )
    raw_text: str | None = Field(default=None, description="Instruction text payload")
    claimed_role_in_text: str | None = Field(
        default=None,
        description="Unverified role claimed inside payload text (e.g. 'I am the manager'). Never upgrades trust!",
    )
    event_id: str | None = Field(default=None, description="Linked event identifier")


class ActionAttemptEvidence(BaseModel):
    """Agent's attempt to call a tool or execute an operation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., description="Tool or action name attempted")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the action"
    )
    timestamp: datetime | None = Field(
        default=None, description="Timestamp of the attempt"
    )
    caller_agent_id: str | None = Field(
        default=None, description="Agent identifier making the attempt"
    )
    event_id: str | None = Field(default=None, description="Event trace ID")


class ToolExecutionEvidence(BaseModel):
    """Result of backend execution of a tool call."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., description="Name of the tool invoked")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments received by backend"
    )
    status: str = Field(
        ...,
        description="Execution status, e.g. 'SUCCESS', 'REJECTED_BY_BACKEND', 'ERROR'",
    )
    rejection_message: str | None = Field(
        default=None,
        description="Backend error or policy rejection message",
    )
    output: Any | None = Field(default=None, description="Return payload from backend")
    event_id: str | None = Field(default=None, description="Event trace ID")


class AuthorizationDecisionEvidence(BaseModel):
    """Explicit authorization or approval record (e.g. manager approval)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="Status: 'APPROVED', 'DENIED', 'PENDING'")
    approver_principal: str | None = Field(
        default=None, description="Approver identity"
    )
    approver_role: str | None = Field(
        default=None, description="Approver role, e.g. 'MANAGER'"
    )
    decision_reason: str | None = Field(
        default=None, description="Justification or approval reason"
    )
    approval_token: str | None = Field(
        default=None, description="Cryptographic or workflow approval token"
    )
    event_id: str | None = Field(default=None, description="Event trace ID")


class DisclosureEvidence(BaseModel):
    """Observation of protected information disclosure."""

    model_config = ConfigDict(extra="forbid")

    marker: str = Field(
        ..., description="Synthetic canary or classification marker disclosed"
    )
    recipient: str = Field(..., description="Observed recipient or channel")
    destination_channel: str = Field(
        ..., description="Destination type, e.g. 'chat_response', 'external_api'"
    )
    content_snippet: str | None = Field(
        default=None, description="Snippet containing disclosed marker"
    )
    event_id: str | None = Field(default=None, description="Event trace ID")


class EffectEvidence(BaseModel):
    """Observable persistent state change on application database or external system."""

    model_config = ConfigDict(extra="forbid")

    target_entity: str = Field(
        ..., description="Entity affected, e.g. 'order_refund', 'user_account'"
    )
    state_change_observed: bool = Field(
        ..., description="Whether a persistent state change occurred"
    )
    committed_status: str = Field(
        ...,
        description="'COMMITTED', 'REVERTED', or 'BLOCKED_NO_CHANGE'",
    )
    delta: dict[str, Any] | None = Field(
        default=None, description="Observed delta/diff"
    )
    event_id: str | None = Field(default=None, description="Event trace ID")


class TraceCompletenessEvidence(BaseModel):
    """Metadata regarding whether the execution trace was fully captured."""

    model_config = ConfigDict(extra="forbid")

    is_complete: bool = Field(
        ..., description="True if full trace from intake to completion was captured"
    )
    missing_stages: list[str] = Field(
        default_factory=list, description="Stages that were truncated or unobserved"
    )
    total_events: int = Field(
        default=0, ge=0, description="Total number of events observed in trace"
    )


class AttackEvidence(BaseModel):
    """Specification of indirect or direct injection attack payload and intention."""

    model_config = ConfigDict(extra="forbid")

    attack_id: str | None = Field(default=None, description="Unique attack ID")
    attack_type: str = Field(
        ..., description="'INDIRECT_PROMPT_INJECTION', 'DIRECT_POLICY_CHALLENGE', etc."
    )
    payload: str = Field(..., description="The injection payload text")
    target_boundary: str = Field(
        default="ATTEMPTED_ACTION", description="Target boundary of attack"
    )
    attacker_goal: str = Field(..., description="Description of attacker objective")


class ExposureEvidence(BaseModel):
    """Explicit observation of whether the agent was exposed to the untrusted content/attack."""

    model_config = ConfigDict(extra="forbid")

    exposure_status: ExposureStatus = Field(
        ...,
        description="'EXPOSED', 'NOT_EXPOSED', or 'UNKNOWN'",
    )
    exposure_event_id: str | None = Field(
        default=None, description="Event where agent read the payload"
    )
    exposure_details: str | None = Field(
        default=None, description="Contextual notes on exposure"
    )


class ArgumentProvenanceEvidence(BaseModel):
    """Optional explicit link showing which instruction source supplied an argument value."""

    model_config = ConfigDict(extra="forbid")

    argument_name: str = Field(..., description="Name of the argument, e.g. 'amount'")
    source_instruction_id: str = Field(
        ..., description="ID of the instruction source supplying the value"
    )
    provenance_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score if computed by provenance tracker",
    )


class EvaluationEvidencePackage(BaseModel):
    """Complete evidence bundle supplied to the C4 policy evaluator."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project ID")
    case_id: str = Field(..., description="Test case ID")
    run_id: str = Field(..., description="Execution run ID")
    trace_id: str | None = Field(default=None, description="Trace ID")
    contract_version: int = Field(
        ..., ge=1, description="Policy contract version to evaluate against"
    )
    origin: EvidenceOrigin = Field(
        default=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE,
        description="Origin of this evidence bundle",
    )
    principal: PrincipalEvidence | None = Field(
        default=None, description="Authenticated principal info"
    )
    instruction_sources: list[InstructionSourceEvidence] = Field(
        default_factory=list,
        description="Instruction sources present in trial",
    )
    action_attempts: list[ActionAttemptEvidence] = Field(
        default_factory=list,
        description="Observed action/tool attempts by agent",
    )
    tool_executions: list[ToolExecutionEvidence] = Field(
        default_factory=list,
        description="Backend tool execution results",
    )
    authorization_decisions: list[AuthorizationDecisionEvidence] = Field(
        default_factory=list,
        description="Observed authorization / approval records",
    )
    disclosures: list[DisclosureEvidence] = Field(
        default_factory=list,
        description="Observed disclosure events",
    )
    effects: list[EffectEvidence] = Field(
        default_factory=list,
        description="Observed state changes and effects",
    )
    trace_completeness: TraceCompletenessEvidence | None = Field(
        default=None,
        description="Trace completeness metadata",
    )
    attacks: list[AttackEvidence] = Field(
        default_factory=list,
        description="Attacks delivered in trial",
    )
    exposure: ExposureEvidence | None = Field(
        default=None,
        description="Exposure observation",
    )
    argument_provenance: list[ArgumentProvenanceEvidence] = Field(
        default_factory=list,
        description="Explicit argument provenance evidence",
    )
    context_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured context dictionary for predicate matching",
    )
