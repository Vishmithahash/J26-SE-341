"""Runtime evidence contract for C2.

Prepares the data structures for Day 2 trace and state observation:
ordered events, tool-call correlation, before/after states, database diffs,
and evidence completeness.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeEvent(BaseModel):
    """An observed agent event (such as a tool call or action) in strict chronological order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_index: int = Field(..., ge=0, description="0-indexed sequence position")
    event_id: str
    tool_call_correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    observable_result: Any = None
    error: str | None = None
    entity_identifiers: dict[str, Any] = Field(
        default_factory=dict,
        description="Identified entity keys, e.g. {'customer_id': 42, 'order_id': 503}",
    )


class StateObservation(BaseModel):
    """Snapshot of application state captured immediately before and after an event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_index: int = Field(..., ge=0)
    before_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Application state observed immediately before the event",
    )
    after_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Application state observed immediately after the event",
    )
    state_diff: dict[str, Any] = Field(
        default_factory=dict,
        description="Explicit changes/deltas between before and after state",
    )


class EvidenceCompleteness(BaseModel):
    """Audit checks confirming that the captured evidence is sufficient for conformance evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    has_all_events: bool = True
    has_state_snapshots: bool = True
    has_db_diffs: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    is_complete: bool = True
    is_truncated: bool = False
    confirmed_agent_termination: bool = True
    termination_reason: str | None = None
    anomalies: list[str] = Field(default_factory=list)


class RuntimeEvidenceContract(BaseModel):
    """Complete runtime evidence packet collected for a single test run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "2026.1"
    project_id: str
    suite_id: str | None = None
    run_id: str
    test_id: str
    model_id: str
    model_version: str
    model_content_hash: str | None = None

    ordered_events: list[RuntimeEvent] = Field(default_factory=list)
    state_observations: list[StateObservation] = Field(default_factory=list)
    completeness: EvidenceCompleteness = Field(default_factory=EvidenceCompleteness)
    execution_mode: str = "synthetic_demonstration"
    collector_provenance: dict[str, Any] = Field(default_factory=dict)
