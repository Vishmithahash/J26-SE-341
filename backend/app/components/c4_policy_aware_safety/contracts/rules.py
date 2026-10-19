from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.artifacts import SourceReference
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    EvaluationBoundary,
    PolicyFamily,
    PolicyRequirement,
    RuleReviewStatus,
    Severity,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.predicates import CompoundPredicate


class ValidationIssue(BaseModel):
    """Validation or derivation issue detected on a candidate rule or contract."""

    model_config = ConfigDict(extra="forbid")

    code: ValidationIssueCode = Field(..., description="Machine-readable issue code")
    message: str = Field(..., description="Human-readable explanation of the issue")
    field: str | None = Field(
        default=None, description="Affected field or path if applicable"
    )
    severity: Severity = Field(
        default=Severity.HIGH, description="Severity of the issue"
    )
    blocking: bool = Field(
        default=True, description="Whether this issue blocks validation/acceptance"
    )


class CandidateRule(BaseModel):
    """Candidate policy rule derived from an artifact or imported for validation."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project ID owning the rule")
    rule_id: str = Field(
        ..., min_length=1, description="Stable unique identifier for the policy rule"
    )
    rule_version: int = Field(default=1, ge=1, description="Rule revision number")
    policy_family: PolicyFamily = Field(
        ...,
        description="Policy family (AUTHORIZATION, CONFIDENTIALITY, INSTRUCTION_AUTHORITY)",
    )
    principal_selector: str = Field(
        ..., description="Role or principal selector, e.g. 'CUSTOMER_SUPPORT' or '*'"
    )
    action_selector: str = Field(
        ..., description="Action or tool selector, e.g. 'process_refund' or '*'"
    )
    resource_selector: str = Field(
        ..., description="Resource selector, e.g. 'order_refund' or '*'"
    )
    applicability_conditions: CompoundPredicate | None = Field(
        default=None,
        description="Conditions determining whether this rule applies to an observed event or context",
    )
    policy_requirement: PolicyRequirement = Field(
        ..., description="ALLOW, DENY, or REQUIRE"
    )
    compliance_conditions: CompoundPredicate = Field(
        ...,
        description="Conditions establishing compliance or violation when rule is applicable",
    )
    evaluation_boundary: EvaluationBoundary = Field(
        ...,
        description="Boundary at which rule is evaluated: ATTEMPTED_ACTION, DISCLOSURE, or COMMITTED_EFFECT",
    )
    required_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence types required to conclusively evaluate this rule",
    )
    severity: Severity = Field(
        default=Severity.HIGH, description="Severity if this policy is violated"
    )
    source_references: list[SourceReference] = Field(
        default_factory=list,
        description="Provenance links to source artifact versions and excerpts",
    )
    validation_issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="Machine-readable issues found during derivation or validation",
    )
    review_status: RuleReviewStatus = Field(
        default=RuleReviewStatus.DRAFT,
        description="Lifecycle review status of candidate rule",
    )
    extraction_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata on extraction method, pattern name, or manual import",
    )


class PolicyRule(BaseModel):
    """Accepted, evaluable, immutable policy rule belonging to an accepted contract."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    rule_id: str
    rule_version: int
    policy_family: PolicyFamily
    principal_selector: str
    action_selector: str
    resource_selector: str
    applicability_conditions: CompoundPredicate | None = None
    policy_requirement: PolicyRequirement
    compliance_conditions: CompoundPredicate
    evaluation_boundary: EvaluationBoundary
    required_evidence: list[str]
    severity: Severity
    source_references: list[SourceReference]
    review_status: RuleReviewStatus = RuleReviewStatus.ACCEPTED
    acceptance_metadata: dict[str, Any] = Field(default_factory=dict)


class ContractCreate(BaseModel):
    """Request payload to create a new contract or draft."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str = Field(
        ..., min_length=1, description="Stable contract identifier"
    )
    rule_ids: list[str] = Field(
        ..., min_length=1, description="List of candidate rule IDs to include"
    )
    description: str | None = Field(
        default=None, description="Contract description or notes"
    )


class ContractAcceptanceRequest(BaseModel):
    """Request payload for explicit contract acceptance."""

    model_config = ConfigDict(extra="forbid")

    accepted_by: str = Field(
        ...,
        min_length=1,
        description="Principal or user explicitly accepting the contract",
    )
    rationale: str | None = Field(
        default=None, description="Acceptance justification or review notes"
    )


class ContractValidationResult(BaseModel):
    """Result of contract validation."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    version: int
    is_valid: bool
    issues: list[ValidationIssue]
    rules_validated_count: int


class PolicyContractVersion(BaseModel):
    """Immutable versioned policy contract."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    project_id: str
    version: int = Field(ge=1)
    lifecycle_state: ContractLifecycleState
    rules: list[PolicyRule]
    referenced_artifact_versions: dict[str, int]
    acceptance_metadata: dict[str, Any] | None = None
    content_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
