"""Pydantic v2 typed contracts for Component 3 Phase 4 recovery evaluation.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    RecoveryContract,
)
from app.components.c3_robustness_recovery.runtime.evidence import MatchedPairEvidence


class RecoveryVerdict(str, Enum):
    """Authoritative deterministic recovery verdicts for eligible fault trials."""

    PASS_COMPLETED = "PASS_COMPLETED"
    PASS_GRACEFUL = "PASS_GRACEFUL"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class RuleEvaluationStatus(str, Enum):
    """Evaluation status of an individual recovery rule."""

    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvaluationStatus(str, Enum):
    """Overall evaluation lifecycle status of a recovery evaluation experiment."""

    EVALUATED = "EVALUATED"
    NOT_EVALUATED = "NOT_EVALUATED"
    EVALUATION_ERROR = "EVALUATION_ERROR"


class C2FactValue(str, Enum):
    """Truth values consumed from Component 2 workflow assertion facts."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class RecoveryRuleId(str, Enum):
    """Canonical rule identifiers evaluated for recovery."""

    RULE_COMPLETION = "RULE_COMPLETION"
    RULE_GRACEFUL_STOPPING = "RULE_GRACEFUL_STOPPING"
    RULE_BUDGETS = "RULE_BUDGETS"
    RULE_DUPLICATE_EFFECTS = "RULE_DUPLICATE_EFFECTS"
    RULE_UNSAFE_RETRIES = "RULE_UNSAFE_RETRIES"
    RULE_TRUTHFUL_COMPLETION = "RULE_TRUTHFUL_COMPLETION"


class C2AssertionFact(BaseModel):
    """Minimal discrete assertion fact consumed from Component 2 or test fixtures.

    C2 owns workflow state-machine evaluation; C3 consumes discrete facts without recomputing domain state.
    """

    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(
        ..., min_length=1, description="Unique assertion identifier defined by C2."
    )
    assertion_version: str = Field(
        "1.0.0", min_length=1, description="Version of the assertion definition."
    )
    value: C2FactValue = Field(
        ..., description="Truth value of the assertion (TRUE, FALSE, or UNKNOWN)."
    )
    entity_id: str | None = Field(
        None, description="Optional entity scope (e.g. order_id, cart_id)."
    )
    snapshot_id: str | None = Field(None, description="Optional snapshot identifier.")
    time_scope: str | None = Field(
        None,
        description="Relevant time scope (e.g. 'initial', 'post_recovery', 'final_state').",
    )
    evaluator_version: str = Field(
        "1.0.0", description="Version of the C2 evaluator or fixture."
    )
    provenance: str = Field(
        "C2_FIXTURE",
        description="Source provenance (e.g. C2_FIXTURE, C2_LIVE_SERVICE).",
    )
    supporting_evidence_refs: list[str] = Field(
        default_factory=list,
        description="References to supporting events, logs, or state snapshots.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Safe metadata or contextual attributes."
    )


class RecoveryRuleResult(BaseModel):
    """Detailed evaluation result for a single recovery rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., description="Stable rule identifier.")
    rule_name: str = Field(..., description="Human-readable rule name.")
    status: RuleEvaluationStatus = Field(..., description="Rule evaluation outcome.")
    reason_code: str | None = Field(None, description="Safe semantic reason code.")
    message: str = Field(..., description="Human-readable explanation of rule result.")
    supporting_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of C2 assertion facts referenced by this rule.",
    )
    supporting_event_ids: list[str] = Field(
        default_factory=list,
        description="IDs of runtime events supporting this rule evaluation.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Rule-specific structured details."
    )


class RecoveryEvaluationRequest(BaseModel):
    """Request model for pure deterministic recovery evaluation."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1, description="Project scope identifier.")
    case_id: str = Field(..., min_length=1, description="Test case identifier.")
    evaluator_version: str = Field(
        "1.1.0", min_length=1, description="Evaluator engine version."
    )
    rule_set_version: str = Field(
        "1.1.0", min_length=1, description="Recovery rule-set version."
    )
    candidate_case: CandidateFaultCase = Field(
        ..., description="Frozen candidate fault case definition."
    )
    recovery_contract: RecoveryContract = Field(
        ..., description="Frozen recovery contract."
    )
    matched_evidence: MatchedPairEvidence = Field(
        ..., description="Linked clean and fault trial evidence."
    )
    c2_facts: list[C2AssertionFact] = Field(
        default_factory=list,
        description="Discrete assertion facts from C2 or test fixtures.",
    )
    suite_fingerprint: str | None = Field(
        None, description="Optional fingerprint of the enclosing suite."
    )
    case_fingerprint: str | None = Field(
        None, description="Optional semantic fingerprint of the case."
    )
    suite_digest: str | None = Field(
        None, description="Optional cryptographic digest of the enclosing suite."
    )
    pinned_mappings: list[Any] | None = Field(
        default=None,
        description="Explicit pinned C2-to-C3 assertion mappings for the project/evaluation.",
    )


class RecoveryEvaluationResult(BaseModel):
    """Comprehensive, explainable recovery evaluation result."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project scope identifier.")
    case_id: str = Field(..., description="Test case identifier.")
    pair_id: str = Field(..., description="Matched trial pair identifier.")
    evaluator_version: str = Field("1.1.0", description="Evaluator engine version.")
    rule_set_version: str = Field("1.1.0", description="Recovery rule-set version.")
    evaluation_status: EvaluationStatus = Field(
        ..., description="Evaluation lifecycle status."
    )
    recovery_verdict: RecoveryVerdict | None = Field(
        None,
        description="Final recovery verdict (null if trial was not eligible for evaluation).",
    )
    case_fingerprint: str | None = Field(
        None, description="Semantic fingerprint of evaluated case."
    )
    suite_digest: str | None = Field(
        None, description="Cryptographic digest of enclosing suite."
    )
    rule_results: list[RecoveryRuleResult] = Field(
        default_factory=list,
        description="Evaluation results for individual recovery rules.",
    )
    first_violated_rule: str | None = Field(
        None, description="Identifier of the first violated rule, if any."
    )
    non_evaluation_reasons: list[str] = Field(
        default_factory=list,
        description="Explicit reasons explaining why evaluation was not performed or failed.",
    )
    clean_control_limitations: list[str] = Field(
        default_factory=list,
        description="Limitations regarding baseline clean-control comparison.",
    )
    demonstration_limitations: list[str] = Field(
        default_factory=list,
        description="Limitations regarding demonstration mode vs live targets.",
    )
    actor_attribution: str = Field(
        "UNKNOWN",
        description="Attributed recovery actor (e.g. SCRIPTED_CALLER, AGENT).",
    )
    evaluated_at_utc: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="UTC timestamp of evaluation execution.",
    )
