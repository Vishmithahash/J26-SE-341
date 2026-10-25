"""Request and response contracts for live NexaCart C3 generation and execution.

Component: C3 - Robustness and Failure Recovery Testing
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.generation import (
    FaultGenerationResponse,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionRecordResponse,
    SuiteRecordResponse,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
)


class LiveTargetReadinessResponse(BaseModel):
    """Live NexaCart harness readiness and the capability manifest built from it."""

    model_config = ConfigDict(extra="forbid")

    target: str = "NexaCart"
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    base_url: str | None = None
    harness_version: str | None = None
    agent: dict[str, Any] | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    supported_combinations_count: int = 0
    tasks: list[dict[str, Any]] = Field(default_factory=list)


class LiveSuiteGenerationRequest(BaseModel):
    """Generate and store a frozen suite from NexaCart's live capabilities."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    task_id: str = Field(default="nxc-refund-cancelled-order", min_length=1)
    max_cases: int = Field(default=8, ge=1, le=50)
    target_tool_ids: list[str] | None = None
    target_fault_families: list[FaultFamily] | None = None
    target_effect_phases: list[EffectPhase] | None = None
    seed: int = Field(default=42, ge=0, le=2_147_483_647)


class LiveSuiteGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation: FaultGenerationResponse
    stored_suite: SuiteRecordResponse | None = None


class LiveExecutionRequest(BaseModel):
    """Start a background live execution of a stored NexaCart suite."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    suite_id_or_digest: str = Field(..., min_length=1)
    case_ids: list[str] | None = Field(
        default=None, description="Subset of suite cases to run (all when omitted)."
    )
    repetitions: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Times each case is run; every repetition is its own matched pair.",
    )
    max_suite_duration_sec: float = Field(default=3600.0, ge=60.0, le=14_400.0)


class LiveExecutionStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ExecutionRecordResponse
    planned_case_ids: list[str]
    note: str
