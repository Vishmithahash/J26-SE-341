"""SQLAlchemy ORM models for C2: State-Aware Multi-Step Workflow Testing.

All component tables are explicitly prefixed with 'c2_'.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

# Use JSONB on postgresql if available, fallback to JSON
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class C2WorkflowModel(Base):
    """Stores versioned workflow EFSM definitions and their approval lifecycle."""

    __tablename__ = "c2_workflow_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(
        String(32), default="2026.1", nullable=False
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full structured EFSM definition stored as JSON/JSONB
    definition: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    # Deterministic canonical content hash of the behavioral definition
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Lifecycle status: DRAFT -> VALIDATED -> APPROVED
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), default="DRAFT", nullable=False, index=True
    )

    # Review & approval metadata
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    validation_reports: Mapped[list["C2ValidationReport"]] = relationship(
        "C2ValidationReport",
        back_populates="model_record",
        cascade="all, delete-orphan",
        order_by="desc(C2ValidationReport.created_at)",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "model_id", "version", name="uq_c2_model_project_id_version"
        ),
        Index("ix_c2_model_lookup", "project_id", "model_id", "version"),
    )


class C2ValidationReport(Base):
    """Stores the structural and bounded semantic validation report for a specific model version."""

    __tablename__ = "c2_validation_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    model_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c2_workflow_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # The exact canonical hash validated
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # READY or NOT_READY

    # Structured details of checks, errors, warnings, and diagnostics
    summary: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    errors: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    diagnostics: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    model_record: Mapped["C2WorkflowModel"] = relationship(
        "C2WorkflowModel",
        back_populates="validation_reports",
    )

    __table_args__ = (
        Index(
            "ix_c2_report_lookup", "project_id", "model_id", "version", "content_hash"
        ),
    )
