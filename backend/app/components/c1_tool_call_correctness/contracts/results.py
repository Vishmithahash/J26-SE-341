from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CorrectnessVerdict(str, Enum):
    """Correctness verdicts for Component 1 evaluations are strictly PASS, FAIL, or INCONCLUSIVE."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class CaseReadinessStatus(str, Enum):
    CONFIGURED = "CONFIGURED"
    UNCONFIGURED = "UNCONFIGURED"
    INVALID_SPEC = "INVALID_SPEC"


class CaseExecutionStatus(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    EXECUTED = "EXECUTED"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    ABORTED = "ABORTED"


class CheckLevelResult(BaseModel):
    """Evaluation result for an individual declarative expectation check."""

    check_id: str = Field(..., description="Unique check identifier")
    rule_name: str = Field(
        ..., description="Name or code of the declarative expectation evaluated"
    )
    target_tool: str | None = Field(
        default=None, description="Tool targeted by this check"
    )
    target_argument: str | None = Field(
        default=None, description="Argument targeted by this check"
    )
    verdict: CorrectnessVerdict = Field(
        ..., description="Check correctness verdict: PASS, FAIL, or INCONCLUSIVE"
    )
    explanation: str = Field(
        ...,
        description="Evidence-backed explanation of why the check passed, failed, or was inconclusive",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="IDs of evidence records corroborating this check result",
    )
    requirement_refs: list[str] = Field(
        default_factory=list,
        description="IDs of task requirements linked to this check",
    )


class CaseVerdictContract(BaseModel):
    """Overall correctness evaluation result for a test case execution."""

    project_id: str = Field(..., description="Owning project ID")
    case_id: str = Field(..., description="Test case ID")
    run_id: str = Field(..., description="Execution run ID")
    requirement_version: str = Field(
        ..., description="Stable requirement version tag evaluated against"
    )
    evaluator_version: str = Field(
        ..., description="Component 1 evaluator engine version"
    )
    code_version: str | None = Field(
        default=None,
        description="Optional repository code commit hash or version. Optional for correctness testing.",
    )
    readiness_status: CaseReadinessStatus = Field(
        ...,
        description="Configuration and spec readiness status, kept distinct from verdict",
    )
    execution_status: CaseExecutionStatus = Field(
        ...,
        description="Runtime execution lifecycle status, kept distinct from verdict",
    )
    verdict: CorrectnessVerdict | None = Field(
        default=None,
        description="Overall correctness verdict. Can only be PASS if case is CONFIGURED and EXECUTED.",
    )
    check_results: list[CheckLevelResult] = Field(
        default_factory=list, description="Individual check-level evaluations"
    )

    @model_validator(mode="after")
    def validate_verdict_consistency(self) -> "CaseVerdictContract":
        """Strict invariance: An unconfigured or unexecuted case must not receive a correctness PASS."""
        if self.verdict == CorrectnessVerdict.PASS:
            if self.readiness_status != CaseReadinessStatus.CONFIGURED:
                raise ValueError(
                    f"Invalid case result: An unconfigured case (readiness='{self.readiness_status}') "
                    f"must not receive a correctness PASS."
                )
            if self.execution_status != CaseExecutionStatus.EXECUTED:
                raise ValueError(
                    f"Invalid case result: An unexecuted case (execution='{self.execution_status}') "
                    f"must not receive a correctness PASS."
                )
        return self
