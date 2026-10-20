from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.enums import EvaluationBoundary
from app.components.c4_policy_aware_safety.contracts.evaluator import EvaluationReport
from app.components.c4_policy_aware_safety.contracts.evidence import (
    EvaluationEvidencePackage,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    PolicyContractVersion,
)


class TestCaseKind(str, Enum):
    """Test case categorization for future C4 generation pipeline."""

    BENIGN = "BENIGN"
    DIRECT_POLICY_CHALLENGE = "DIRECT_POLICY_CHALLENGE"
    INDIRECT_PROMPT_INJECTION = "INDIRECT_PROMPT_INJECTION"


class PolicyTestCaseStub(BaseModel):
    """Contract for future generated C4 test cases separating agent payload from oracle goals."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., description="Unique test case ID")
    project_id: str = Field(..., description="Project ID")
    test_kind: TestCaseKind = Field(
        ..., description="BENIGN, DIRECT_POLICY_CHALLENGE, or INDIRECT_PROMPT_INJECTION"
    )
    target_rule_id: str = Field(
        ..., description="Policy rule ID targeted by this test case"
    )
    target_rule_version: int = Field(..., description="Policy rule version targeted")
    contract_version: int = Field(..., description="Contract version")

    # Agent-facing task payload (what the agent sees)
    agent_task_prompt: str = Field(
        ..., description="User prompt or task input given to the agent"
    )
    injection_placement_channel: str | None = Field(
        default=None,
        description="Channel where indirect injection is placed, e.g. support_ticket, tool_response, retrieved_doc",
    )
    injection_payload: str | None = Field(
        default=None,
        description="Injection text embedded in untrusted source (empty for benign)",
    )

    # Hidden expected outcomes and attacker goals (never revealed to agent)
    expected_boundary: EvaluationBoundary = Field(
        ..., description="Expected evaluation boundary"
    )
    hidden_attacker_goal: str | None = Field(
        default=None,
        description="Attacker objective, kept strictly separate from agent task payload",
    )
    expected_policy_verdict: str = Field(
        ..., description="Expected policy verdict (PASS, FAIL, etc.)"
    )
    required_evidence_fixtures: list[str] = Field(
        default_factory=list,
        description="Fixture identifiers needed for this test case",
    )


@runtime_checkable
class PolicyExtractionProvider(Protocol):
    """Protocol for future LLM-assisted policy extraction providers."""

    def extract_candidates(
        self,
        artifact: ArtifactVersionRecord,
        options: dict[str, Any] | None = None,
    ) -> list[CandidateRule]:
        """Extract candidate rules from an artifact version."""
        ...


@runtime_checkable
class ExecutionEvidenceConsumer(Protocol):
    """Protocol for consuming execution traces from shared run orchestrator in future phases."""

    def consume_run_trace(
        self,
        raw_trace_events: list[dict[str, Any]],
        contract: PolicyContractVersion,
    ) -> EvaluationEvidencePackage:
        """Transform raw shared runtime events into a normalized C4 evidence package."""
        ...


@runtime_checkable
class ReportingExporter(Protocol):
    """Protocol for exporting evaluation findings to shared framework report in future phases."""

    def export_report(self, report: EvaluationReport) -> dict[str, Any]:
        """Export evaluation report to shared reporting schema."""
        ...
