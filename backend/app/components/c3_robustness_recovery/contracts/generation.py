"""Generation policy, request/response, and frozen-suite contracts for Component 3.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    RecoveryContract,
    SafeStr,
    TaskFixtureMetadata,
    ValidationReason,
    ValidationScope,
)


class GenerationStatus(str, Enum):
    """Overall status of candidate fault case generation."""

    GENERATED = "GENERATED"
    NO_FEASIBLE_CASES = "NO_FEASIBLE_CASES"
    TEST_NOT_READY = "TEST_NOT_READY"


class GenerationPolicy(BaseModel):
    """Deterministic generation and selection policy."""

    model_config = ConfigDict(extra="forbid")

    max_cases: StrictInt = Field(default=10, ge=1, le=50)
    max_candidates_examined: StrictInt = Field(default=200, ge=1, le=1000)
    seed: StrictInt = Field(default=42, ge=0, le=2_147_483_647)
    selection_seed: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    content_seed: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    target_fault_families: list[FaultFamily] | None = None
    target_tool_ids: list[SafeStr] | None = None
    target_effect_phases: list[EffectPhase] | None = None
    coverage_strategy: SafeStr = Field(default="ROUND_ROBIN", max_length=64)


class GenerationCounters(BaseModel):
    """Explicit population counters tracking generation search and selection."""

    model_config = ConfigDict(extra="forbid")

    examined_count: StrictInt = 0
    valid_count: StrictInt = 0
    rejected_count: StrictInt = 0
    duplicate_count: StrictInt = 0
    unique_count: StrictInt = 0
    selected_count: StrictInt = 0
    truncated: StrictBool = False
    truncation_reason: SafeStr | None = None

    @property
    def selected_cases_count(self) -> int:
        return self.selected_count

    @property
    def examined_candidates_count(self) -> int:
        return self.examined_count


class FrozenSuite(BaseModel):
    """Immutable, reproducible frozen test suite with canonical digest and case fingerprints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SafeStr = "1.0.0"
    suite_id: SafeStr = Field(min_length=1, max_length=128)
    generator_version: SafeStr = "1.0.0"
    seed: StrictInt
    policy: GenerationPolicy

    task_fixture_metadata: TaskFixtureMetadata
    adapter_manifest: AdapterCapabilityManifest
    recovery_contract: RecoveryContract

    selected_cases: list[CandidateFaultCase] = Field(default_factory=list)
    case_fingerprints: dict[str, SafeStr] = Field(default_factory=dict)
    suite_digest: SafeStr = Field(min_length=64, max_length=64)

    counters: GenerationCounters
    limitations: list[SafeStr] = Field(default_factory=list)


class FaultGenerationRequest(BaseModel):
    """Request payload for automatic feasible fault case generation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SafeStr = "1.0.0"
    project_id: SafeStr = Field(default="proj-demo-qa", max_length=128)
    task_id: SafeStr | None = None
    task_version: SafeStr | None = None
    tool_id: SafeStr | None = None
    tool_version: SafeStr | None = None
    domain: SafeStr = Field(default="ecommerce", max_length=64)
    task_fixture_metadata: TaskFixtureMetadata
    adapter_manifest: AdapterCapabilityManifest
    recovery_contract: RecoveryContract
    policy: GenerationPolicy = Field(default_factory=GenerationPolicy)


class FaultGenerationResponse(BaseModel):
    """Response payload for automatic generation, strictly static and unexecuted."""

    model_config = ConfigDict(extra="forbid")

    validation_scope: ValidationScope = ValidationScope.STATIC_ONLY
    generation_status: GenerationStatus
    frozen_suite: FrozenSuite | None = None
    counters: GenerationCounters
    reasons: list[ValidationReason] = Field(default_factory=list)
    pending_checks: list[SafeStr] = Field(default_factory=list)
    runtime_verified: Literal[False] = False
    execution_ready: Literal[False] = False
    recovery_verdict: None = None


class ModelAssistedDraftRequest(BaseModel):
    """Request payload for drafting structured inputs via the selected LLM."""

    model_config = ConfigDict(extra="forbid")

    project_id: SafeStr = Field(default="proj-demo-qa", max_length=128)
    task_id: SafeStr | None = None
    task_version: SafeStr | None = "1.0.0"
    tool_id: SafeStr | None = None
    tool_version: SafeStr | None = "1.0.0"
    domain: SafeStr = Field(default="ecommerce", max_length=64)
    instructions: SafeStr | None = None
    existing_task_fixture: TaskFixtureMetadata | None = None
    existing_adapter_manifest: AdapterCapabilityManifest | None = None
    existing_recovery_contract: RecoveryContract | None = None


class ModelAssistedDraftResponse(BaseModel):
    """Response payload with model-drafted structured inputs and resolution metadata."""

    model_config = ConfigDict(extra="forbid")

    status: SafeStr  # "SUCCESS" | "UNRESOLVED_REFERENCES" | "FAILED"
    draft_task_fixture: TaskFixtureMetadata | None = None
    draft_adapter_manifest: AdapterCapabilityManifest | None = None
    draft_recovery_contract: RecoveryContract | None = None
    unresolved_references: list[SafeStr] = Field(default_factory=list)
    explanation: SafeStr | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
