"""Contracts for C4 Phase 4 onboarding orchestration across domain profiles."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.bindings import (
    DomainBinding,
    SyntheticFixture,
)


class OnboardingJobStatus(str, Enum):
    STARTED = "STARTED"
    EXTRACTION_COMPLETE = "EXTRACTION_COMPLETE"
    CANDIDATES_REVIEWED = "CANDIDATES_REVIEWED"
    DRAFT_CONTRACT_BUILT = "DRAFT_CONTRACT_BUILT"
    CONTRACT_ACCEPTED = "CONTRACT_ACCEPTED"
    TESTS_GENERATED = "TESTS_GENERATED"
    CASES_FROZEN = "CASES_FROZEN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OnboardingStep(str, Enum):
    INITIALIZE = "INITIALIZE"
    EXTRACT_CANDIDATES = "EXTRACT_CANDIDATES"
    REVIEW_CANDIDATES = "REVIEW_CANDIDATES"
    BUILD_DRAFT_CONTRACT = "BUILD_DRAFT_CONTRACT"
    ACCEPT_CONTRACT = "ACCEPT_CONTRACT"
    GENERATE_AND_FREEZE_CASES = "GENERATE_AND_FREEZE_CASES"
    VERIFY_RUNTIME_READINESS = "VERIFY_RUNTIME_READINESS"
    EXECUTE_TESTS = "EXECUTE_TESTS"


class OnboardingJobCreate(BaseModel):
    """Payload to initiate an end-to-end policy onboarding workflow."""

    model_config = ConfigDict(extra="forbid")

    domain_id: str = Field(..., description="Target domain profile ('domain-ecommerce-c4' or 'domain-booking-c4')")
    artifact_id: str = Field(..., description="Policy artifact identifier")
    artifact_version: int = Field(default=1, ge=1, description="Version of the source policy artifact")
    binding_id: str = Field(..., description="Domain binding ID matching domain profile")
    binding_version: int = Field(default=1, ge=1, description="Domain binding version")
    provider_id: str = Field(
        default="shared_llm",
        description="Extraction provider ('shared_llm' = selected QA model, Ollama by default; 'offline_mock' for tests)",
    )
    reviewer: str = Field(default="dev_reviewer", description="Reviewer identifier for acceptance boundary")
    is_synthetic_review: bool = Field(
        default=True, description="True if using simulated/development reviewer metadata"
    )


class DomainProfileDefinition(BaseModel):
    """Authoritative domain profile declaration."""

    model_config = ConfigDict(extra="forbid")

    domain_id: str = Field(..., description="Unique domain identifier")
    name: str = Field(..., description="Human-readable domain name")
    description: str = Field(..., description="Domain description")
    binding: DomainBinding = Field(..., description="Authoritative domain bindings")
    sample_policy_markdown: str = Field(..., description="Canonical representative policy text")
    synthetic_fixtures: list[SyntheticFixture] = Field(
        default_factory=list, description="Synthetic fixtures registered for this domain"
    )
    capabilities: set[str] = Field(default_factory=set, description="Observed runtime capabilities")
    adapter_id: str = Field(..., description="Default adapter identifier")
    adapter_version: str = Field(..., description="Default adapter version")
    is_live_available: bool = Field(default=False, description="Whether live AUT environment is connected")
    live_blockers: list[str] = Field(
        default_factory=list, description="Explicit reasons why live AUT execution is blocked"
    )


class C4OnboardingJobRecord(BaseModel):
    """Persisted record of an onboarding pipeline execution."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Unique onboarding job ID")
    project_id: str = Field(..., description="Project ID")
    domain_id: str = Field(..., description="Domain identifier")
    binding_id: str = Field(..., description="Domain binding identifier")
    binding_version: int = Field(..., description="Domain binding version")
    artifact_id: str = Field(..., description="Source policy artifact ID")
    artifact_version: int = Field(..., description="Source policy artifact version")
    extraction_job_id: str | None = Field(default=None, description="Linked extraction job ID")
    draft_contract_id: str | None = Field(default=None, description="Draft contract ID")
    contract_version: int | None = Field(default=None, description="Contract version")
    batch_id: str | None = Field(default=None, description="Generated case batch ID")
    status: OnboardingJobStatus = Field(default=OnboardingJobStatus.STARTED)
    current_step: OnboardingStep = Field(default=OnboardingStep.INITIALIZE)
    step_results: dict[str, Any] = Field(default_factory=dict, description="Results from completed steps")
    gaps: list[dict[str, Any]] = Field(
        default_factory=list, description="Unsupported rules or coverage gaps identified"
    )
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
