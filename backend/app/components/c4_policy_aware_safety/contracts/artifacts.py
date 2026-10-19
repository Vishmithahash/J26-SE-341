from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c4_policy_aware_safety.contracts.enums import ArtifactKind


class ArtifactSection(BaseModel):
    """Identified section within a normalized artifact."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(
        ..., description="Stable section identifier, e.g. 'sec-refund-limits'"
    )
    title: str = Field(..., description="Section title or heading")
    content: str = Field(..., description="Text content of the section")
    start_char: int | None = Field(
        default=None, description="Starting character offset in artifact"
    )
    end_char: int | None = Field(
        default=None, description="Ending character offset in artifact"
    )


class SourceReference(BaseModel):
    """Source reference linking a rule to an exact artifact version and span."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., description="Project ID owning the source artifact")
    artifact_id: str = Field(..., description="Source artifact ID")
    artifact_version: int = Field(
        ..., ge=1, description="Exact immutable version of the source artifact"
    )
    section_id: str | None = Field(
        default=None, description="Referenced section ID if applicable"
    )
    start_char: int | None = Field(
        default=None, description="Exact start character span"
    )
    end_char: int | None = Field(default=None, description="Exact end character span")
    supporting_excerpt: str = Field(
        ...,
        min_length=1,
        description="Exact quote/excerpt from the artifact proving provenance",
    )
    evidence_reference: str | None = Field(
        default=None,
        description="Optional cross-reference identifier in existing evidence registry",
    )


class ArtifactCreate(BaseModel):
    """Payload to register an artifact version."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(
        ..., min_length=1, description="Stable identifier for the artifact"
    )
    artifact_kind: ArtifactKind = Field(..., description="Kind of artifact")
    raw_content: str = Field(
        ..., min_length=1, description="Raw content (text/markdown or JSON string)"
    )
    sections: list[ArtifactSection] | None = Field(
        default=None,
        description="Optional explicitly identified sections. If omitted, text artifacts are automatically sectioned.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Creation and intake metadata"
    )


class ArtifactVersionRecord(BaseModel):
    """Persisted, immutable artifact version record."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    artifact_id: str
    artifact_kind: ArtifactKind
    version: int
    content_hash: str
    normalized_content: str
    sections: list[ArtifactSection]
    metadata: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
