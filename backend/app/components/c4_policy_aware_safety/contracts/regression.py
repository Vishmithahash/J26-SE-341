"""Contracts and data models for Phase 5 Policy Change Tracking, Diffing, and Selective Regression."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleChangeType(str, Enum):
    """Classification of changes between policy rule versions."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    SEMANTICALLY_MODIFIED = "SEMANTICALLY_MODIFIED"
    METADATA_ONLY = "METADATA_ONLY"
    PROVENANCE_ONLY = "PROVENANCE_ONLY"
    UNCHANGED = "UNCHANGED"
    UNCERTAIN = "UNCERTAIN"


class CaseImpactLevel(str, Enum):
    """Impact level of policy change on existing test cases."""

    DEFINITELY_AFFECTED = "DEFINITELY_AFFECTED"
    POSSIBLY_AFFECTED = "POSSIBLY_AFFECTED"
    UNAFFECTED = "UNAFFECTED"
    UNSUPPORTED = "UNSUPPORTED"


class CaseDecisionAction(str, Enum):
    """Action to take on a test case in response to policy changes."""

    REGENERATE = "REGENERATE"
    REVALIDATE = "REVALIDATE"
    RETIRE = "RETIRE"
    REVISE = "REVISE"
    RETAIN = "RETAIN"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class PlanLifecycleState(str, Enum):
    """Lifecycle state of a regression plan."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    FROZEN = "FROZEN"
    EXECUTED = "EXECUTED"


class ExecutionModeType(str, Enum):
    """Execution mode for regression cases."""

    FRESH_EXECUTION = "FRESH_EXECUTION"
    HISTORICAL_RE_EVALUATION = "HISTORICAL_RE_EVALUATION"
    REUSED_HISTORICAL = "REUSED_HISTORICAL"


class VerdictTransitionType(str, Enum):
    """Type of verdict transition between baseline and candidate policy."""

    PASS_TO_PASS = "PASS_TO_PASS"
    PASS_TO_FAIL = "PASS_TO_FAIL"
    FAIL_TO_PASS = "FAIL_TO_PASS"
    FAIL_TO_FAIL = "FAIL_TO_FAIL"
    PASS_TO_INCONCLUSIVE = "PASS_TO_INCONCLUSIVE"
    FAIL_TO_INCONCLUSIVE = "FAIL_TO_INCONCLUSIVE"
    INCONCLUSIVE_TO_PASS = "INCONCLUSIVE_TO_PASS"
    INCONCLUSIVE_TO_FAIL = "INCONCLUSIVE_TO_FAIL"
    NEW_COVERAGE = "NEW_COVERAGE"
    RETIRED = "RETIRED"


class RuleDiffRecord(BaseModel):
    """Detailed diff for a single policy rule."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    change_type: RuleChangeType
    baseline_rule_version: int | None = None
    candidate_rule_version: int | None = None
    change_description: str
    field_changes: dict[str, Any] = Field(default_factory=dict)
    affects_boundary: bool = False
    affects_approval: bool = False
    affects_permission: bool = False
    affects_confidentiality: bool = False
    affects_instruction_authority: bool = False


class PolicyComparisonRequest(BaseModel):
    """Request payload to compare two accepted policy contracts."""

    project_id: str
    baseline_contract_id: str
    baseline_contract_version: int
    candidate_contract_id: str
    candidate_contract_version: int
    domain_id: str | None = None
    binding_id: str | None = None
    binding_version: int | None = None
    fixture_versions: dict[str, int] = Field(default_factory=dict)


class PolicyComparisonRecord(BaseModel):
    """Immutable record of policy contract comparison."""

    model_config = ConfigDict(frozen=True)

    comparison_id: str
    project_id: str
    baseline_contract_id: str
    baseline_contract_version: int
    baseline_contract_hash: str
    candidate_contract_id: str
    candidate_contract_version: int
    candidate_contract_hash: str
    rule_diffs: list[RuleDiffRecord]
    summary: dict[str, int]
    algorithm_version: str = "c4_diff_v1"
    configuration_digest: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CaseImpactDecision(BaseModel):
    """Impact analysis decision for a specific test case."""

    case_id: str
    case_version: int
    target_rule_id: str
    test_kind: str
    impact_level: CaseImpactLevel
    action: CaseDecisionAction
    reason: str
    dependent_rule_ids: list[str] = Field(default_factory=list)
    replacement_case_id: str | None = None
    replacement_case_version: int | None = None
    predecessor_case_id: str | None = None
    predecessor_case_version: int | None = None


class RegressionPlanRecord(BaseModel):
    """Versioned regression plan containing impact decisions and proposed replacements."""

    plan_id: str
    project_id: str
    comparison_id: str
    baseline_contract_id: str
    baseline_contract_version: int
    candidate_contract_id: str
    candidate_contract_version: int
    binding_id: str
    binding_version: int
    status: PlanLifecycleState = PlanLifecycleState.DRAFT
    case_decisions: list[CaseImpactDecision]
    proposed_replacement_cases: list[str] = Field(default_factory=list)
    retained_cases: list[str] = Field(default_factory=list)
    retired_cases: list[str] = Field(default_factory=list)
    readiness_gaps: list[str] = Field(default_factory=list)
    dependency_hashes: dict[str, str] = Field(default_factory=dict)
    plan_digest: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    frozen_at: datetime | None = None


class VerdictTransition(BaseModel):
    """Transition of a test verdict between policy versions."""

    case_id: str
    rule_id: str
    baseline_verdict: str | None
    candidate_verdict: str
    transition_type: VerdictTransitionType
    explanation: str
    is_requirement_change: bool = False


class RegressionReport(BaseModel):
    """Evidence-linked regression report."""

    report_id: str
    project_id: str
    plan_id: str
    comparison_id: str
    baseline_contract_id: str
    baseline_contract_version: int
    candidate_contract_id: str
    candidate_contract_version: int
    diff_summary: dict[str, int]
    impact_summary: dict[str, int]
    execution_summary: dict[str, int]
    verdict_transitions: list[VerdictTransition]
    per_rule_findings: list[dict[str, Any]]
    injection_target_findings: list[dict[str, Any]]
    attempt_goal_outcomes: dict[str, int]
    commit_goal_outcomes: dict[str, int]
    benign_utility_summary: dict[str, int]
    readiness_failures: list[str]
    baseline_denominator: int
    candidate_denominator: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RegressionBatchRecord(BaseModel):
    """Record of selective regression execution batch."""

    batch_id: str
    project_id: str
    plan_id: str
    candidate_contract_id: str
    candidate_contract_version: int
    adapter_id: str
    execution_mode: ExecutionModeType
    executed_run_ids: list[str] = Field(default_factory=list)
    reused_run_ids: list[str] = Field(default_factory=list)
    historical_re_eval_ids: list[str] = Field(default_factory=list)
    status: str = "COMPLETED"
    report: RegressionReport | None = None
    idempotency_key: str | None = None
    request_digest: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class HistoricalReEvaluationRequest(BaseModel):
    """Request to re-evaluate historical run evidence under candidate policy."""

    project_id: str
    plan_id: str
    run_ids: list[str] = Field(default_factory=list)
