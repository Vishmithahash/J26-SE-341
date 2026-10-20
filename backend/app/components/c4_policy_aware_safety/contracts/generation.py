from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.future import TestCaseKind


class GenerationConfig(BaseModel):
    """Configuration options controlling bounded deterministic test generation."""

    model_config = ConfigDict(extra="forbid")

    categories: list[TestCaseKind] = Field(
        default_factory=lambda: [
            TestCaseKind.BENIGN,
            TestCaseKind.DIRECT_POLICY_CHALLENGE,
            TestCaseKind.INDIRECT_PROMPT_INJECTION,
        ],
        description="Case categories to generate",
    )
    target_rule_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of contract rule IDs to target. If None, targets all rules.",
    )
    seed: int = Field(default=42, description="RNG seed for reproducible variants")
    max_cases_per_rule: int = Field(
        default=10, ge=1, le=50, description="Generation budget cap per rule"
    )
    include_benign_controls: bool = Field(
        default=True, description="Whether to generate matched benign source controls for injections"
    )
    include_boundary_values: bool = Field(
        default=True, description="Whether to generate equality boundary cases for thresholds"
    )


class GenerationRequest(BaseModel):
    """API payload to trigger automatic test generation."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str = Field(..., min_length=1, description="Accepted policy contract ID")
    contract_version: int = Field(..., ge=1, description="Exact accepted contract version")
    binding_id: str = Field(..., min_length=1, description="Domain binding ID")
    binding_version: int = Field(..., ge=1, description="Exact domain binding version")
    config: GenerationConfig = Field(
        default_factory=GenerationConfig, description="Generation parameters"
    )
    auto_validate: bool = Field(
        default=True, description="Whether to automatically run independent validation"
    )
    auto_freeze: bool = Field(
        default=False, description="Whether to freeze validated cases immediately"
    )


class GenerationReport(BaseModel):
    """Structured report summarizing the generation batch results and coverage."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(..., description="Unique generation batch ID")
    project_id: str = Field(..., description="Project ID")
    contract_id: str = Field(..., description="Policy contract ID")
    contract_version: int = Field(..., description="Policy contract version")
    binding_id: str = Field(..., description="Domain binding ID")
    binding_version: int = Field(..., description="Domain binding version")
    seed: int = Field(..., description="Seed used for batch")
    config_digest: str = Field(..., description="SHA-256 digest of generation parameters")
    requested_rules: list[str] = Field(default_factory=list)
    requested_categories: list[str] = Field(default_factory=list)
    generated_count: int = Field(default=0, ge=0)
    validated_count: int = Field(default=0, ge=0)
    frozen_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    review_needed_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    unsupported_rules: list[str] = Field(default_factory=list)
    readiness_gaps: list[str] = Field(default_factory=list)
    budget_omissions: list[str] = Field(default_factory=list)
    planned_coverage: dict[str, list[str]] = Field(default_factory=dict)
    case_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
