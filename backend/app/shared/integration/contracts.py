"""Strict versioned integration contracts for cross-component orchestration and reporting.

Component: Shared Integration Foundation (Part 1)
Scope: Versioned schemas for run plans, component references, identifier correlation,
       runtime observations, component evaluations, and integration readiness.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntegrationPlanStatus(str, Enum):
    """Lifecycle state of an integration run plan."""

    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ComponentType(str, Enum):
    """The four research components comprising the modular monolith."""

    C1 = "C1"  # Tool-Call Correctness & Diagnosis
    C2 = "C2"  # State-Aware Workflow (EFSM)
    C3 = "C3"  # Robustness & Failure Recovery
    C4 = "C4"  # Policy-Aware Safety & Prompt Injection


class NativeEntityType(str, Enum):
    """Native entity types referenced from independent components."""

    CONFIG = "CONFIG"
    MODEL = "MODEL"
    SUITE = "SUITE"
    CASE = "CASE"
    PAIR = "PAIR"
    TRIAL = "TRIAL"
    RUN = "RUN"
    CONTRACT = "CONTRACT"
    EVAL = "EVAL"


class ReadinessSeverity(str, Enum):
    """Severity classification for integration readiness issues."""

    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    LIMITATION = "LIMITATION"


class ReadinessIssueCode(str, Enum):
    """Explicit, machine-readable reason codes for readiness assessment."""

    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    UNAPPROVED_MODEL = "UNAPPROVED_MODEL"
    CROSS_PROJECT_REFERENCE = "CROSS_PROJECT_REFERENCE"
    UNFROZEN_SUITE = "UNFROZEN_SUITE"
    INCOMPATIBLE_FIXTURE = "INCOMPATIBLE_FIXTURE"
    EMPTY_SUITE = "EMPTY_SUITE"
    INVALID_DIGEST = "INVALID_DIGEST"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    SUITE_NOT_FOUND = "SUITE_NOT_FOUND"
    CONTRACT_NOT_FOUND = "CONTRACT_NOT_FOUND"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    TEST_NOT_FOUND = "TEST_NOT_FOUND"
    TEST_NOT_READY = "TEST_NOT_READY"
    AMBIGUOUS_SELECTION = "AMBIGUOUS_SELECTION"
    UNAPPROVED_CONTRACT = "UNAPPROVED_CONTRACT"
    INCOMPLETE_PLAN_SEMANTICS = "INCOMPLETE_PLAN_SEMANTICS"
    INVALID_POLICY_RULES = "INVALID_POLICY_RULES"
    UNACCEPTED_CONTRACT = "UNACCEPTED_CONTRACT"


class ReadinessVerdict(str, Enum):
    """Overall readiness verdict for an integration run plan."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    PARTIALLY_READY = "PARTIALLY_READY"


# ---------------------------------------------------------------------------
# Component Configuration and Case References
# ---------------------------------------------------------------------------


class C1ConfigReference(BaseModel):
    """Reference to a Component 1 validated project configuration or suite version."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project scoping identifier")
    config_id: str = Field(..., description="C1 project configuration record ID")
    config_version: int = Field(
        default=1, description="C1 configuration version number"
    )
    suite_id: str | None = Field(default=None, description="Optional promoted suite ID")
    suite_version: int | None = Field(
        default=None, description="Optional suite version"
    )
    frozen_content_hash: str | None = Field(
        default=None, description="Deterministic content hash of config or suite"
    )
    agent_connection_ref: str | None = Field(
        default=None, description="Referenced agent target endpoint/adapter"
    )
    tool_names: list[str] = Field(
        default_factory=list, description="Allowlisted tools declared in this config"
    )
    case_id: str | None = Field(
        default=None, description="Optional pinned candidate test case ID"
    )


class C2ModelReference(BaseModel):
    """Reference to a Component 2 approved EFSM workflow model or test suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project scoping identifier")
    model_id: str = Field(..., description="EFSM model identifier")
    model_version: str = Field(default="1.0.0", description="Semantic model version")
    suite_id: str | None = Field(
        default=None, description="Generated suite ID if already compiled"
    )
    frozen_content_hash: str | None = Field(
        default=None, description="Deterministic content hash of approved EFSM"
    )
    lifecycle_status: str | None = Field(
        default=None,
        description="Model approval lifecycle (must be APPROVED for execution)",
    )
    task_ref: str | None = Field(
        default=None, description="Primary workflow task reference"
    )
    test_id: str | None = Field(
        default=None, description="Specific generated test definition ID"
    )


class C3SuiteReference(BaseModel):
    """Reference to a Component 3 frozen fault recovery test suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project scoping identifier")
    suite_id: str = Field(..., description="Fault suite identifier")
    suite_digest: str = Field(..., description="Immutable SHA256 frozen suite digest")
    task_id: str | None = Field(default=None, description="Task fixture identifier")
    target_tool_id: str | None = Field(
        default=None, description="Fault injection target tool"
    )
    total_cases: int = Field(
        default=0, description="Total candidate fault cases in suite"
    )
    case_id: str | None = Field(
        default=None, description="Specific candidate fault case ID"
    )
    expected_entity_id: str | None = Field(
        default=None, description="Expected entity ID for scoped C2 assertions"
    )


class C4PolicyReference(BaseModel):
    """Reference to a Component 4 approved policy contract or frozen safety suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project scoping identifier")
    contract_id: str | None = Field(
        default=None, description="Policy contract identifier"
    )
    contract_version: int | None = Field(default=None, description="Contract version")
    suite_id: str | None = Field(
        default=None, description="Frozen policy safety suite ID"
    )
    suite_version: int | None = Field(default=None, description="Suite version")
    frozen_content_hash: str | None = Field(
        default=None,
        description="Deterministic hash of approved policy contract or suite",
    )
    lifecycle_state: str | None = Field(
        default=None, description="Contract lifecycle state (must be APPROVED/ACTIVE)"
    )
    case_id: str | None = Field(default=None, description="Policy test case ID")


class ComponentReferencesPlan(BaseModel):
    """Unified collection of native component references for an integration plan."""

    model_config = ConfigDict(extra="forbid")

    c1: C1ConfigReference | None = Field(
        default=None, description="Component 1 tool correctness reference"
    )
    c2: C2ModelReference | None = Field(
        default=None, description="Component 2 state-aware workflow reference"
    )
    c3: C3SuiteReference | None = Field(
        default=None, description="Component 3 robustness & recovery reference"
    )
    c4: C4PolicyReference | None = Field(
        default=None, description="Component 4 safety & policy reference"
    )


# ---------------------------------------------------------------------------
# Identifier Mapping and Correlation
# ---------------------------------------------------------------------------


class CorrelationMapping(BaseModel):
    """Explicit mapping between a shared integration run and a native component entity."""

    model_config = ConfigDict(extra="forbid")

    component: ComponentType = Field(..., description="Source component")
    native_entity_type: NativeEntityType = Field(
        ..., description="Native entity classification"
    )
    native_id: str = Field(..., description="Original component-native identifier")
    step_or_trial_index: int | None = Field(
        default=None, description="Ordered step or trial index within the shared run"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Component-specific contextual attributes"
    )


class ExecutionTrialCorrelation(BaseModel):
    """Correlated trial plan linking native component executions within an integration run."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(..., description="Unique correlation identifier")
    trial_mappings: list[CorrelationMapping] = Field(
        default_factory=list,
        description="Native entity mappings associated with this correlation",
    )


# ---------------------------------------------------------------------------
# Runtime Events, Observation References, and Evaluations
# ---------------------------------------------------------------------------


class ObservedEventReference(BaseModel):
    """Cross-component reference to a runtime event observed during execution."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="Unique event identifier")
    integration_run_id: str = Field(
        ..., description="Shared integration run identifier"
    )
    source_component: ComponentType = Field(
        ..., description="Component originating the event"
    )
    event_type: str = Field(
        ...,
        description="Event classification (e.g. TOOL_CALL_CAPTURED, STATE_TRANSITION, FAULT_INJECTED, POLICY_EVALUATED)",
    )
    timestamp_utc: datetime = Field(..., description="Event timestamp in UTC")
    payload_digest: str = Field(
        ..., description="SHA256 digest of normalized event payload"
    )
    observation_scope: dict[str, Any] = Field(
        default_factory=dict,
        description="Scoping metadata (tool_name, turn_index, states, hooks)",
    )


class ComponentEvaluationReference(BaseModel):
    """Reference to an evaluator result produced by an independent component."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(..., description="Unique shared evaluation reference ID")
    component: ComponentType = Field(..., description="Evaluating component")
    native_run_id: str = Field(..., description="Component native run identifier")
    native_eval_id: str = Field(
        ..., description="Component native evaluation record ID"
    )
    verdict: str = Field(..., description="Component-native verdict preserved as-is")
    verdict_precedence: int = Field(
        default=0, description="Precedence rank of the verdict for summary aggregation"
    )
    evidence_digest: str = Field(
        ..., description="Digest of retained component evidence"
    )


class RelatedFindingLink(BaseModel):
    """Cross-component link connecting related findings without modifying research ownership."""

    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(..., description="Unique link identifier")
    integration_run_id: str = Field(
        ..., description="Shared integration run identifier"
    )
    source_component: ComponentType = Field(
        ..., description="Component observing the primary finding"
    )
    target_component: ComponentType = Field(
        ..., description="Component observing the related finding"
    )
    relation_type: str = Field(
        ...,
        description="Correlation type (e.g. CAUSED_BY, CORRELATED_WITH, PRECEDING_STATE_VIOLATION, UNRECOVERED_POLICY_BREACH)",
    )
    source_finding_id: str = Field(
        ..., description="Native finding identifier in source component"
    )
    target_finding_id: str = Field(
        ..., description="Native finding identifier in target component"
    )
    rationale: str = Field(
        ..., description="Explanation of cross-component correlation"
    )


# ---------------------------------------------------------------------------
# Integration Readiness and Limitations
# ---------------------------------------------------------------------------


class ComponentReadinessIssue(BaseModel):
    """Detailed description of an issue discovered during readiness evaluation."""

    model_config = ConfigDict(extra="forbid")

    component: ComponentType = Field(..., description="Affected component")
    issue_code: ReadinessIssueCode = Field(
        ..., description="Machine-readable issue code"
    )
    message: str = Field(..., description="Human-readable issue explanation")
    severity: ReadinessSeverity = Field(..., description="Severity of the issue")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Supplementary debugging context"
    )


class ComponentReadinessSummary(BaseModel):
    """Per-component readiness summary."""

    model_config = ConfigDict(extra="forbid")

    component: ComponentType = Field(..., description="Evaluated component")
    is_ready: bool = Field(
        ..., description="Whether this component meets all readiness gates"
    )
    native_ref_id: str | None = Field(
        default=None, description="Referenced entity ID if found"
    )
    frozen_digest: str | None = Field(
        default=None, description="Frozen content or suite digest"
    )
    issues: list[ComponentReadinessIssue] = Field(
        default_factory=list, description="Readiness issues for this component"
    )


class IntegrationReadinessReport(BaseModel):
    """Complete readiness evaluation report across all referenced components."""

    model_config = ConfigDict(extra="forbid")

    is_ready: bool = Field(..., description="True if no blocking issues exist")
    verdict: ReadinessVerdict = Field(..., description="Overall readiness verdict")
    checked_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    component_statuses: dict[str, ComponentReadinessSummary] = Field(
        default_factory=dict, description="Status keyed by component (C1, C2, C3, C4)"
    )
    blocking_issues: list[ComponentReadinessIssue] = Field(
        default_factory=list,
        description="List of all blocking issues across components",
    )
    warnings: list[ComponentReadinessIssue] = Field(
        default_factory=list, description="Non-blocking warnings or limitations"
    )


# ---------------------------------------------------------------------------
# API Request and Response Contracts
# ---------------------------------------------------------------------------


class IntegrationRunPlanCreateRequest(BaseModel):
    """Request payload to create a new shared integration run plan."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Plan title/name")
    description: str | None = Field(
        default=None, description="Optional description of the test plan"
    )
    c1_reference: C1ConfigReference | None = Field(
        default=None, description="Optional C1 reference"
    )
    c2_reference: C2ModelReference | None = Field(
        default=None, description="Optional C2 reference"
    )
    c3_reference: C3SuiteReference | None = Field(
        default=None, description="Optional C3 reference"
    )
    c4_reference: C4PolicyReference | None = Field(
        default=None, description="Optional C4 reference"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Supplementary orchestration metadata"
    )


class IntegrationRunPlanResponse(BaseModel):
    """Full representation of a persisted integration run plan."""

    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(..., description="Primary record UUID")
    integration_run_id: str = Field(
        ..., description="Shared integration run identifier (irun-...)"
    )
    project_id: str = Field(..., description="Project scope")
    name: str = Field(..., description="Plan title")
    description: str | None = Field(default=None, description="Plan description")
    schema_version: str = Field(default="2026.1", description="Contract schema version")
    lifecycle_status: IntegrationPlanStatus = Field(..., description="Plan status")
    plan_digest: str = Field(
        ..., description="Deterministic SHA256 digest of frozen plan"
    )
    created_by_user_id: int | None = Field(default=None, description="Creator user ID")
    created_at_utc: datetime = Field(..., description="Creation timestamp in UTC")
    updated_at_utc: datetime = Field(..., description="Last update timestamp in UTC")
    component_references: ComponentReferencesPlan = Field(
        ..., description="Frozen component references"
    )
    identifier_mappings: list[CorrelationMapping] = Field(
        default_factory=list, description="Native-to-shared identifier mappings"
    )
    readiness_report: IntegrationReadinessReport = Field(
        ..., description="Complete readiness evaluation report"
    )


class IntegrationPlanListResponse(BaseModel):
    """Paginated list of integration run plans."""

    model_config = ConfigDict(extra="ignore")

    items: list[IntegrationRunPlanResponse] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)


class ReadinessCheckRequest(BaseModel):
    """Ad-hoc readiness validation request without persisting a run plan."""

    model_config = ConfigDict(extra="forbid")

    c1_reference: C1ConfigReference | None = Field(default=None)
    c2_reference: C2ModelReference | None = Field(default=None)
    c3_reference: C3SuiteReference | None = Field(default=None)
    c4_reference: C4PolicyReference | None = Field(default=None)


class ExecutionStartRequest(BaseModel):
    """Request payload to execute a frozen integration run plan."""

    model_config = ConfigDict(extra="forbid")

    target_mode: str = Field(
        default="CONTROLLED_TEST",
        description="Execution mode: 'CONTROLLED_TEST' or 'LIVE_AUT'",
    )
    timeout_seconds: int = Field(
        default=60, ge=1, le=600, description="Execution timeout in seconds"
    )
    max_tool_calls: int = Field(
        default=50, ge=1, le=200, description="Max tool calls budget"
    )
    task_prompt_override: str | None = Field(
        default=None, description="Optional override for natural language agent prompt"
    )
    permitted_tools_override: list[str] | None = Field(
        default=None, description="Optional override for allowlisted tools"
    )


class ExecutionStatusResponse(BaseModel):
    """Execution status and projected multi-evaluator outcome."""

    model_config = ConfigDict(extra="ignore")

    execution_id: str
    integration_run_id: str
    project_id: str
    lifecycle_status: str
    target_mode: str
    plan_digest: str
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    retained_evidence_digest: str | None = None
    evaluations: dict[str, Any] = Field(default_factory=dict)
    cleanup_successful: bool | None = None
    cleanup_reusable: bool | None = None
    error_message: str | None = None


class ExecutionListResponse(BaseModel):
    """List of execution records for an integration plan."""

    model_config = ConfigDict(extra="ignore")

    items: list[ExecutionStatusResponse] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)


# ---------------------------------------------------------------------------
# Combined QA Reporting, Finding Linkage, and Evidence Replay Contracts
# ---------------------------------------------------------------------------


class ComponentContribution(BaseModel):
    """Standardized component contribution within a combined QA report."""

    model_config = ConfigDict(extra="ignore")

    component: ComponentType = Field(..., description="Component identifier")
    native_entity_id: str = Field(..., description="Referenced entity ID")
    evaluation_version: str = Field(
        default="2026.1", description="Evaluation contract/schema version"
    )
    evaluator_version: str = Field(
        default="1.0.0", description="Evaluator engine version"
    )
    status: str = Field(
        ...,
        description="Status: EVALUATED, NOT_EVALUATED, NOT_READY, BLOCKED, FAILED",
    )
    native_verdict: str | None = Field(
        default=None,
        description="Native component verdict without flattening into generic PASS/FAIL",
    )
    checks_or_rules_count: int = Field(
        default=0, description="Total checks or rules executed"
    )
    violations_or_findings_count: int = Field(
        default=0, description="Total violations or findings recorded"
    )
    native_details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed component-specific results"
    )
    evidence_references: list[str] = Field(
        default_factory=list, description="Sanitized evidence identifiers"
    )
    non_evaluation_reasons: list[str] = Field(
        default_factory=list, description="Reasons if component was not evaluated"
    )


class UnifiedFinding(BaseModel):
    """An individual finding or violation recorded by a component."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(
        ..., description="Deterministic unique identifier for deduplication"
    )
    component: ComponentType = Field(
        ..., description="Originating component (C1, C2, C3, C4)"
    )
    rule_or_check_id: str = Field(..., description="Check, rule, or transition ID")
    native_verdict: str = Field(..., description="Native component verdict")
    severity: str = Field(
        default="VIOLATION",
        description="Severity: INFO, WARNING, VIOLATION, CRITICAL",
    )
    event_id: str | None = Field(default=None, description="Correlated event reference")
    tool_call_id: str | None = Field(
        default=None, description="Correlated tool call identifier"
    )
    entity_id: str | None = Field(
        default=None, description="Correlated domain entity ID"
    )
    message: str = Field(..., description="Finding description or failure reason")
    supporting_evidence: dict[str, Any] | None = Field(
        default=None, description="Supporting evidence excerpt"
    )


class CorrelatedFindingGroup(BaseModel):
    """Group of distinct component findings linked through shared event or entity references."""

    model_config = ConfigDict(extra="ignore")

    group_id: str = Field(..., description="Unique cluster ID")
    correlation_key: str = Field(
        ..., description="Correlation key e.g. event:<id> or entity:<id>"
    )
    shared_entity_or_event_ref: str = Field(
        ..., description="Shared entity or event reference"
    )
    finding_ids: list[str] = Field(
        default_factory=list, description="IDs of linked findings"
    )
    involved_components: list[ComponentType] = Field(
        default_factory=list, description="Components involved in this group"
    )
    findings: list[UnifiedFinding] = Field(
        default_factory=list, description="Distinct individual findings (uncollapsed)"
    )
    correlation_explanation: str = Field(
        ..., description="Explanation of why these findings are correlated"
    )


class ReportCompletenessSummary(BaseModel):
    """Completeness metrics and component coverage breakdown for the run."""

    model_config = ConfigDict(extra="ignore")

    requested_components: list[ComponentType] = Field(
        default_factory=list, description="Components requested in run plan"
    )
    evaluated_components: list[ComponentType] = Field(
        default_factory=list, description="Components that actually evaluated evidence"
    )
    not_ready_components: list[ComponentType] = Field(
        default_factory=list, description="Components that failed readiness"
    )
    blocked_components: list[ComponentType] = Field(
        default_factory=list, description="Components blocked from running"
    )
    failed_execution_components: list[ComponentType] = Field(
        default_factory=list, description="Components that failed during execution"
    )
    not_evaluated_components: list[ComponentType] = Field(
        default_factory=list, description="Components in plan that were not evaluated"
    )
    pending_or_missing_evidence: list[str] = Field(
        default_factory=list, description="Identified missing evidence or gaps"
    )
    per_component_verdicts: dict[str, str] = Field(
        default_factory=dict, description="Native verdict per component"
    )
    per_component_counts: dict[str, int] = Field(
        default_factory=dict, description="Total checks count per component"
    )
    overall_verdict: str = Field(
        ...,
        description="Overall verdict (PASSED, FAILED, PARTIAL, BLOCKED, NOT_EVALUATED)",
    )


class CombinedQAReport(BaseModel):
    """Combined cross-component QA report consolidating all evaluated findings."""

    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(..., description="Unique report identifier")
    integration_run_id: str = Field(..., description="Shared integration run ID")
    execution_id: str = Field(..., description="Execution identifier")
    project_id: str = Field(..., description="Project scoping identifier")
    target_mode: str = Field(
        default="CONTROLLED_TEST",
        description="Execution mode (CONTROLLED_TEST/LIVE_AUT)",
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict, description="Runner, environment, and provenance details"
    )
    generated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Report generation timestamp in UTC",
    )
    completeness: ReportCompletenessSummary = Field(
        ..., description="Completeness summary"
    )
    component_contributions: dict[str, ComponentContribution] = Field(
        default_factory=dict, description="Per-component contributions"
    )
    raw_finding_count: int = Field(
        default=0, description="Raw total count of individual findings"
    )
    grouped_defect_count: int = Field(
        default=0,
        description="Count of distinct defect groups / correlated incident clusters",
    )
    findings: list[UnifiedFinding] = Field(
        default_factory=list, description="Uncollapsed individual findings"
    )
    correlated_defect_groups: list[CorrelatedFindingGroup] = Field(
        default_factory=list, description="Correlated finding groups"
    )
    report_digest: str = Field(
        ..., description="Deterministic SHA256 content digest of combined report"
    )


class ReplayComparisonResponse(BaseModel):
    """Deterministic comparison between original execution evaluation and evidence replay."""

    model_config = ConfigDict(extra="ignore")

    execution_id: str = Field(..., description="Execution ID replayed")
    is_semantically_identical: bool = Field(
        ..., description="True if semantic verdicts and counts match exactly"
    )
    original_evaluations: dict[str, Any] = Field(
        default_factory=dict, description="Evaluations stored in original run"
    )
    replayed_evaluations: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluations produced by replaying retained evidence",
    )
    semantic_diffs: list[str] = Field(
        default_factory=list, description="Differences found if any"
    )
    divergence_reasons: list[str] = Field(
        default_factory=list, description="Detailed reasons for semantic divergence"
    )
    nondeterministic_fields_ignored: list[str] = Field(
        default_factory=list,
        description="Non-deterministic fields excluded from equality comparison",
    )
    replayed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of replay in UTC",
    )


class IntegrationReportListResponse(BaseModel):
    """Paginated list of combined QA reports."""

    model_config = ConfigDict(extra="ignore")

    items: list[CombinedQAReport] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)
