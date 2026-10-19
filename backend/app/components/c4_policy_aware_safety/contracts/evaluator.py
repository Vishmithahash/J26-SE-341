from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.artifacts import SourceReference
from app.components.c4_policy_aware_safety.contracts.enums import (
    AttackOutcome,
    BenignUtilityOutcome,
    Severity,
    Verdict,
    ViolationStage,
)


class RuleEvaluationFinding(BaseModel):
    """Detailed evaluation finding for a single policy rule against supplied evidence."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(..., description="Unique finding ID")
    component_id: str = Field(
        default="C4", description="Authoritative component identifier"
    )
    project_id: str = Field(..., description="Project ID")
    case_id: str = Field(..., description="Test case ID")
    run_id: str = Field(..., description="Execution run ID")
    contract_id: str = Field(..., description="Policy contract ID")
    contract_version: int = Field(..., description="Policy contract version")
    rule_id: str = Field(..., description="Policy rule ID")
    rule_version: int = Field(..., description="Policy rule version")
    verdict: Verdict = Field(
        ..., description="Evaluation verdict: PASS, FAIL, INCONCLUSIVE, NOT_EXERCISED"
    )
    reason_codes: list[str] = Field(
        default_factory=list, description="Machine-readable verdict reason codes"
    )
    severity: Severity = Field(..., description="Policy rule severity")
    source_policy_reference: SourceReference | None = Field(
        default=None, description="Provenance link to source policy"
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of evidence events supporting this verdict",
    )
    violation_stage: ViolationStage | None = Field(
        default=None,
        description="Stage where violation was established: ATTEMPTED_PROHIBITED_ACTION, COMPLETED_PROHIBITED_ACTION_OR_EFFECT, etc.",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="List of evidence types that were missing or inconclusive",
    )
    observed_effect: str | None = Field(
        default=None,
        description="Explicit description of observed effect or explicit unknown marker",
    )
    explanation: str = Field(
        ..., description="Concise human-readable explanation of finding"
    )
    attack_outcome: AttackOutcome = Field(
        default=AttackOutcome.NOT_APPLICABLE,
        description="Attacker objective outcome (BLOCKED, ACHIEVED, etc.), tracked separately from policy verdict",
    )
    benign_utility: BenignUtilityOutcome = Field(
        default=BenignUtilityOutcome.UNKNOWN,
        description="Benign task completion status, tracked separately from safety policy verdict",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvaluationReport(BaseModel):
    """Aggregated evaluation report across all rules in a contract for an evidence package."""

    model_config = ConfigDict(extra="forbid")

    component_id: str = Field(default="C4")
    project_id: str
    case_id: str
    run_id: str
    contract_id: str
    contract_version: int
    overall_verdict: Verdict
    findings: list[RuleEvaluationFinding]
    summary: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
