import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import EvaluationBoundary
from app.components.c4_policy_aware_safety.contracts.future import (
    PolicyTestCaseStub,
)
from app.components.c4_policy_aware_safety.contracts.rules import ValidationIssue


class CaseLifecycleState(str, Enum):
    """Lifecycle progression of a generated policy test case."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    FROZEN = "FROZEN"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ExpectedAssertion(BaseModel):
    """Per-rule expected applicability and compliance assertion."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., description="Target policy rule ID")
    rule_version: int = Field(default=1, ge=1, description="Target policy rule version")
    expected_applicability: str = Field(
        ..., description="'EXERCISED' or 'NOT_EXERCISED'"
    )
    expected_compliance: str = Field(
        ..., description="Expected compliance for safe agent: 'PASS', 'FAIL', or 'INCONCLUSIVE'"
    )
    expected_violation_on_compromise: str | None = Field(
        default="FAIL",
        description="Expected policy compliance verdict if agent is compromised by attack",
    )
    derivation_basis: str = Field(
        default="DETERMINISTIC_POLICY_ANALYSIS",
        description="Basis for expectation (e.g. 'DETERMINISTIC_POLICY_ANALYSIS', 'INDEPENDENT_REVIEW')",
    )
    notes: str | None = Field(default=None, description="Explanation of expected outcome")


class AgentVisiblePayload(BaseModel):
    """Strictly bounded view exposed to the agent under test.

    Hidden attacker goals, internal assertions, and fixture mutations are excluded.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int
    agent_task_prompt: str
    visible_context: dict[str, Any] = Field(default_factory=dict)
    available_tools: list[str] = Field(default_factory=list)


class HarnessPayload(BaseModel):
    """Execution instructions for test harness only.

    Includes setup, preconditions, fixture references, and untrusted payload placement.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int
    fixture_ids: list[str] = Field(default_factory=list)
    fixture_setup: dict[str, Any] = Field(default_factory=dict)
    injection_placement_channel: str | None = None
    injection_payload: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    untrusted_source_id: str | None = None
    declared_evidence_capabilities: list[str] = Field(default_factory=list)


class EvaluatorPayload(BaseModel):
    """Oracle expectations for policy evaluator only.

    Kept strictly hidden from agent instructions.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int
    contract_id: str
    contract_version: int
    target_rule_ids: list[str] = Field(default_factory=list)
    expected_boundary: EvaluationBoundary
    expected_assertions: list[ExpectedAssertion] = Field(default_factory=list)
    hidden_attacker_goal: str | None = None
    expected_policy_verdict: str
    requested_action_legality: str = "PERMITTED"
    expected_safe_behavior: str = "EXECUTE"
    attacker_objective_verdict: str | None = None
    derivation_basis: str = "DETERMINISTIC_POLICY_ANALYSIS"

    @property
    def evaluation_boundary(self) -> EvaluationBoundary:
        return self.expected_boundary


class PolicyTestCase(PolicyTestCaseStub):
    """Concrete, versioned, executable policy test case.

    Extends PolicyTestCaseStub while providing scenario-group linking,
    versioned dependencies, separated payloads, and canonical hashing.
    """

    model_config = ConfigDict(extra="forbid")

    case_version: int = Field(default=1, ge=1, description="Immutable case revision number")
    domain_id: str = Field(..., description="Target domain binding ID")
    binding_version: int = Field(default=1, ge=1, description="Domain binding version")
    scenario_group_id: str = Field(
        ..., description="Identifier linking related benign, challenge, and injection variants"
    )
    contract_id: str = Field(..., description="Target accepted contract ID")
    target_rule_ids: list[str] = Field(
        default_factory=list, description="All policy rules exercised or evaluated by this case"
    )
    target_rule_versions: dict[str, int] = Field(
        default_factory=dict, description="Map of rule_id to rule_version"
    )
    supporting_artifact_dependencies: dict[str, int] = Field(
        default_factory=dict, description="Map of artifact_id to artifact_version"
    )
    fixture_versions: dict[str, int] = Field(
        default_factory=dict, description="Map of fixture_id to fixture_version"
    )
    generator_id: str = Field(
        default="c4_policy_test_generator", description="Identifier of generator"
    )
    generator_version: str = Field(
        default="2.0.0", description="Generator implementation version"
    )
    config_digest: str = Field(
        default="", description="Digest of generation configuration"
    )
    seed: int = Field(default=42, description="RNG seed for deterministic generation")
    variant_id: str = Field(
        ..., description="Deterministic variant identifier (e.g. 'variant-benign-below-limit')"
    )
    legitimate_task: str = Field(
        ..., description="Human-readable legitimate task description"
    )
    structured_setup: dict[str, Any] = Field(
        default_factory=dict, description="Structured setup facts and initial states"
    )
    preconditions: list[str] = Field(
        default_factory=list, description="Preconditions required for execution"
    )
    expected_assertions: list[ExpectedAssertion] = Field(
        default_factory=list, description="Explicit per-rule expected assertions"
    )
    assertion_derivation_basis: str = Field(
        default="DETERMINISTIC_POLICY_ANALYSIS",
        description="'DETERMINISTIC_POLICY_ANALYSIS' or 'INDEPENDENT_REVIEW'",
    )
    required_evidence: list[str] = Field(
        default_factory=list, description="Allowlisted evidence categories needed to evaluate"
    )
    is_obsolete: bool = Field(
        default=False, description="Flag indicating obsolete or superseded test specification"
    )
    validation_issues: list[ValidationIssue] = Field(
        default_factory=list, description="Static validation issues found on this case"
    )
    lifecycle_state: CaseLifecycleState = Field(
        default=CaseLifecycleState.DRAFT,
        description="Current lifecycle state (DRAFT, VALIDATED, FROZEN, REJECTED, NEEDS_REVIEW)",
    )
    content_hash: str = Field(default="", description="SHA-256 canonical case content hash")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    frozen_at: datetime | None = Field(default=None, description="Timestamp when case was frozen")

    def build_agent_visible_payload(self) -> AgentVisiblePayload:
        """Export agent-visible payload only; excludes hidden goals and oracle assertions."""
        visible_ctx = {
            k: v
            for k, v in self.structured_setup.items()
            if not k.startswith("hidden_") and not k.startswith("_")
        }
        return AgentVisiblePayload(
            case_id=self.case_id,
            case_version=self.case_version,
            agent_task_prompt=self.agent_task_prompt,
            visible_context=visible_ctx,
            available_tools=list(self.structured_setup.get("available_tools", [])),
        )

    def build_harness_payload(self) -> HarnessPayload:
        """Export harness-only instructions including fixture IDs and injection placement."""
        return HarnessPayload(
            case_id=self.case_id,
            case_version=self.case_version,
            fixture_ids=self.required_evidence_fixtures,
            fixture_setup=self.structured_setup,
            injection_placement_channel=self.injection_placement_channel,
            injection_payload=self.injection_payload,
            preconditions=self.preconditions,
            untrusted_source_id=self.structured_setup.get("untrusted_source_id"),
            declared_evidence_capabilities=self.required_evidence,
        )

    def build_evaluator_payload(self) -> EvaluatorPayload:
        """Export evaluator-only payload containing oracle assertions and hidden comparison data."""
        return EvaluatorPayload(
            case_id=self.case_id,
            case_version=self.case_version,
            contract_id=self.contract_id,
            contract_version=self.contract_version,
            target_rule_ids=self.target_rule_ids or [self.target_rule_id],
            expected_boundary=self.expected_boundary,
            expected_assertions=self.expected_assertions,
            hidden_attacker_goal=self.hidden_attacker_goal,
            expected_policy_verdict=self.expected_policy_verdict,
            requested_action_legality=self.requested_action_legality,
            expected_safe_behavior=self.expected_safe_behavior,
            attacker_objective_verdict=self.attacker_objective_verdict,
            derivation_basis=self.assertion_derivation_basis,
        )

    def compute_content_hash(self) -> str:
        """Compute canonical SHA-256 hash of immutable semantic contents."""
        semantic_data = {
            "case_id": self.case_id,
            "case_version": self.case_version,
            "domain_id": self.domain_id,
            "binding_version": self.binding_version,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "test_kind": self.test_kind.value,
            "variant_id": self.variant_id,
            "target_rule_ids": sorted(self.target_rule_ids or [self.target_rule_id]),
            "agent_task_prompt": self.agent_task_prompt,
            "injection_placement_channel": self.injection_placement_channel,
            "injection_payload": self.injection_payload,
            "expected_boundary": self.expected_boundary.value,
            "hidden_attacker_goal": self.hidden_attacker_goal,
            "expected_policy_verdict": self.expected_policy_verdict,
            "requested_action_legality": self.requested_action_legality,
            "expected_safe_behavior": self.expected_safe_behavior,
            "attacker_objective_verdict": self.attacker_objective_verdict,
            "is_obsolete": self.is_obsolete,
            "structured_setup": self.structured_setup,
            "preconditions": sorted(self.preconditions),
            "expected_assertions": [a.model_dump(mode="json") for a in self.expected_assertions],
            "required_evidence": sorted(self.required_evidence),
        }
        canon_json = json.dumps(semantic_data, sort_keys=True)
        return hashlib.sha256(canon_json.encode("utf-8")).hexdigest()
