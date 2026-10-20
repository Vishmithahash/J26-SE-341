"""Contracts for baseline comparisons (B1 Final-state, B2 Trace-only, B3 Milestone, B4 Full C2)."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    FirstDivergenceDetail,
    RuntimeVerdict,
    ViolationDetail,
)


class BaselineType(str, Enum):
    """The four comparative evaluation methods evaluated in C2 research."""

    B1_FINAL_STATE_ONLY = "B1_FINAL_STATE_ONLY"
    B2_TRACE_ONLY = "B2_TRACE_ONLY"
    B3_MILESTONE_BASED = "B3_MILESTONE_BASED"
    B4_FULL_C2 = "B4_FULL_C2"


class EvidenceProjectionType(str, Enum):
    """Evidence projection boundary applied to isolate baseline inputs."""

    FINAL_STATE_AND_OUTCOME_ONLY = "FINAL_STATE_AND_OUTCOME_ONLY"
    ORDERED_EVENTS_ONLY = "ORDERED_EVENTS_ONLY"
    MILESTONE_CHECKPOINTS_ONLY = "MILESTONE_CHECKPOINTS_ONLY"
    FULL_PERMITTED_EVIDENCE = "FULL_PERMITTED_EVIDENCE"


class BaselinePredictionContract(BaseModel):
    """Standardized prediction and diagnostic contract across all evaluation baselines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method_id: BaselineType
    method_name: str
    method_version: str = "2026.1"
    evidence_projection: EvidenceProjectionType

    verdict: RuntimeVerdict
    reasons: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    violations: list[ViolationDetail] = Field(default_factory=list)

    can_localize_first_divergence: bool = False
    first_divergence: FirstDivergenceDetail | None = None
    predicted_divergence_event_id: str | None = None
    predicted_divergence_step: int | None = None
    divergence_localization_unavailable_reason: str | None = None

    evaluator_timing_ms: float = 0.0
    source_evidence_digest: str = ""
    evidence_digest_consumed: str = ""
    detailed_coverage: Any = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
