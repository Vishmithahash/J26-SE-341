import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.correction import (
    CandidatePatch,
    ReviewRecord,
    VerificationCheckResult,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CheckLevelResult,
    CorrectnessVerdict,
)

# Sensitive keys and patterns to redact
SENSITIVE_KEY_PATTERNS = [
    r"api[_-]?key",
    r"auth[_-]?token",
    r"bearer[_-]?token",
    r"secret",
    r"password",
    r"credential",
    r"database_url",
    r"aws[_-]",
    r"openai[_-]",
]


def redact_sensitive_fields(obj: Any) -> Any:
    """Recursively traverses dictionaries, lists, or strings and redacts sensitive credentials."""
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            if any(
                re.search(pat, str(k), re.IGNORECASE) for pat in SENSITIVE_KEY_PATTERNS
            ):
                redacted[k] = "[REDACTED_CREDENTIAL]"
            else:
                redacted[k] = redact_sensitive_fields(v)
        return redacted
    elif isinstance(obj, list):
        return [redact_sensitive_fields(elem) for elem in obj]
    elif isinstance(obj, str):
        # Check if entire string looks like an authorization header / secret
        if any(
            re.search(pat, obj, re.IGNORECASE)
            for pat in [r"^bearer\s+[a-zA-Z0-9_\-\.]{15,}", r"^sk-[a-zA-Z0-9]{20,}"]
        ):
            return "[REDACTED_SECRET]"
        return obj
    return obj


class ExportFormat(str, Enum):
    JSON = "JSON"
    CSV = "CSV"


class WorkflowReportFilter(BaseModel):
    """Filters for paginated workflow reporting and data exports."""

    project_id: str
    run_id: str | None = None
    suite_id: str | None = None
    verdict: CorrectnessVerdict | None = None
    cause_category: CauseCategory | None = None
    is_verified: bool | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class WorkflowCaseReportItem(BaseModel):
    """Unified, end-to-end audit record for a single test case across all pipeline stages."""

    case_id: str
    suite_id: str | None = None
    run_id: str
    attempt_number: int = 1
    session_id: str | None = None

    # Inputs & frozen requirements
    prompt_template: str | None = None
    requirement_refs: list[str] = Field(default_factory=list)

    # Execution & Trace
    execution_status: CaseExecutionStatus
    verdict: CorrectnessVerdict
    trace_completeness: TraceCompleteness = TraceCompleteness.COMPLETE
    error_message: str | None = None
    duration_ms: float = 0.0

    # Declarative check results (expected vs observed)
    check_results: list[CheckLevelResult] = Field(default_factory=list)

    # Explanation stage
    explanation_summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    source_relationship: str | None = None

    # Diagnosis stage
    cause_category: CauseCategory | None = None
    diagnosis_confidence: float | None = None
    candidate_code_locations: list[CandidateCodeLocation] = Field(default_factory=list)
    diagnosis_evidence_refs: list[str] = Field(default_factory=list)

    # Candidate correction stage
    correction_attempted: bool = False
    candidate_patch: CandidatePatch | None = None
    is_verified: bool = False
    verification_checks: list[VerificationCheckResult] = Field(default_factory=list)

    # Developer review stage
    review: ReviewRecord | None = None


class WorkflowRunReport(BaseModel):
    """Comprehensive, machine-readable report for an execution run or project suite."""

    project_id: str
    run_id: str | None = None
    suite_id: str | None = None
    suite_version: int | None = None
    config_version: int | None = None

    # Aggregate outcome metrics
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    inconclusive_cases: int = 0

    # Diagnostic & Correction breakdown
    total_diagnosed: int = 0
    application_code_defects_count: int = 0
    agent_behaviour_defects_count: int = 0
    specification_problem_count: int = 0
    unknown_cause_count: int = 0

    total_corrections_attempted: int = 0
    verified_corrections_count: int = 0
    accepted_corrections_count: int = 0
    rejected_corrections_count: int = 0

    # Pagination & items
    items: list[WorkflowCaseReportItem] = Field(default_factory=list)
    total_count: int = 0
    limit: int = 50
    offset: int = 0
    has_next: bool = False
