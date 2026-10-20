from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.validation import ValidationIssue


class CandidateCaseStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class EvidenceRef(BaseModel):
    """Stable pointer to recorded evidence captured during an execution run."""

    evidence_id: str = Field(..., description="Unique evidence record identifier")
    channel: EvidenceChannel = Field(..., description="Evidence recording channel")
    uri_or_pointer: str = Field(
        ..., description="URI or storage pointer to raw evidence payload"
    )
    checksum: str | None = Field(
        default=None, description="SHA256 checksum of evidence content"
    )
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str | None = Field(
        default=None, description="Short summary of observed evidence"
    )


class ToolCallEvent(BaseModel):
    """Recorded tool-call event captured from agent execution."""

    event_id: str = Field(..., description="Uniform event identifier, e.g. evt_01H...")
    run_id: str = Field(..., description="Associated execution run ID")
    call_index: int = Field(
        ..., ge=0, description="0-indexed sequence position of the call"
    )
    tool_name: str = Field(..., description="Invoked tool name")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Captured raw arguments payload"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="Pointers to trace/log entries corroborating this tool call",
    )


class ExecutionAttempt(BaseModel):
    attempt_id: str = Field(..., description="Unique attempt ID")
    attempt_number: int = Field(
        default=1, ge=1, description="Sequential attempt number"
    )
    status: RunStatus = Field(default=RunStatus.PENDING)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)


class ExecutionRun(BaseModel):
    run_id: str = Field(..., description="Uniform run identifier")
    project_id: str = Field(..., description="Associated project ID")
    suite_version_id: str = Field(
        ..., description="ID of the accepted suite version executed"
    )
    status: RunStatus = Field(default=RunStatus.PENDING)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
    attempts: list[ExecutionAttempt] = Field(default_factory=list)


class CandidateCase(BaseModel):
    """Candidate test case before or during promotion to an accepted suite."""

    case_id: str = Field(..., description="Uniform case identifier")
    project_id: str = Field(..., description="Owning project ID")
    config_version: int = Field(
        ..., ge=1, description="Component configuration version targeted"
    )
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    user_request: str = Field(
        ..., min_length=1, description="Simulated end-user prompt or intent"
    )
    status: CandidateCaseStatus = Field(default=CandidateCaseStatus.DRAFT)
    expected_tool_calls: list[str] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)


class AcceptedCaseVersion(BaseModel):
    """Immutable snapshot of a case approved for test execution."""

    case_id: str = Field(...)
    version: int = Field(default=1, ge=1)
    frozen_config_id: str = Field(
        ..., description="ID of the immutable project config snapshot"
    )
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuiteVersion(BaseModel):
    """Accepted and immutable collection of test cases bound to a configuration snapshot."""

    suite_id: str = Field(..., description="Suite identifier")
    project_id: str = Field(..., description="Owning project ID")
    version: int = Field(default=1, ge=1)
    name: str = Field(..., min_length=1)
    config_id: str = Field(
        ..., description="Referenced C1ProjectConfigModel snapshot ID"
    )
    case_versions: list[AcceptedCaseVersion] = Field(default_factory=list)
    is_immutable: bool = Field(
        default=True, description="Accepted suite versions are strictly immutable"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
