"""SQLAlchemy ORM models for Shared Integration Run Plans, Identifier Mappings, and Artifact References.

Component: Shared Integration Foundation (Part 1)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class IntegrationRunPlanModel(Base):
    """Additive persistence for shared cross-component integration run plans."""

    __tablename__ = "integration_run_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    integration_run_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(
        String(32), default="2026.1", nullable=False
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), default="PLANNED", index=True, nullable=False
    )
    plan_digest: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Full structured frozen plan payload and readiness report stored as JSON
    plan_payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    readiness_report: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    identifier_mappings: Mapped[list["IntegrationIdentifierMappingModel"]] = (
        relationship(
            "IntegrationIdentifierMappingModel",
            back_populates="run_plan",
            cascade="all, delete-orphan",
            order_by="IntegrationIdentifierMappingModel.id",
        )
    )
    artifact_references: Mapped[list["IntegrationArtifactReferenceModel"]] = (
        relationship(
            "IntegrationArtifactReferenceModel",
            back_populates="run_plan",
            cascade="all, delete-orphan",
            order_by="IntegrationArtifactReferenceModel.id",
        )
    )


class IntegrationIdentifierMappingModel(Base):
    """Additive persistence for mapping shared integration run identifiers to component native IDs."""

    __tablename__ = "integration_identifier_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("integration_run_plans.integration_run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    component_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    native_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    native_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    step_or_trial_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run_plan: Mapped["IntegrationRunPlanModel"] = relationship(
        "IntegrationRunPlanModel", back_populates="identifier_mappings"
    )

    __table_args__ = (
        UniqueConstraint(
            "integration_run_id",
            "component_type",
            "native_entity_type",
            "native_id",
            name="uq_integration_id_mapping",
        ),
    )


class IntegrationArtifactReferenceModel(Base):
    """Additive persistence for artifact and evidence pointers attached to an integration run."""

    __tablename__ = "integration_artifact_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("integration_run_plans.integration_run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    component_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    artifact_category: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    meta_data: Mapped[dict | None] = mapped_column("metadata", JSON_TYPE, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run_plan: Mapped["IntegrationRunPlanModel"] = relationship(
        "IntegrationRunPlanModel", back_populates="artifact_references"
    )
