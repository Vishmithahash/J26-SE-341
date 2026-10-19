"""SQLAlchemy ORM models for C2: State-Aware Multi-Step Workflow Testing.

All component tables are explicitly prefixed with 'c2_'.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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
    test_suites: Mapped[list["C2TestSuite"]] = relationship(
        "C2TestSuite",
        back_populates="model_record",
        cascade="all, delete-orphan",
        order_by="desc(C2TestSuite.created_at)",
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


class C2TestSuite(Base):
    """Stores generated test suites associated with an approved model version."""

    __tablename__ = "c2_test_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c2_workflow_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    generator_version: Mapped[str] = mapped_column(
        String(32), default="c2_generator_v1", nullable=False
    )
    seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)

    config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    diagnostics: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ready_cases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_ready_cases_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    category_counts: Mapped[dict] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    model_record: Mapped["C2WorkflowModel"] = relationship(
        "C2WorkflowModel", back_populates="test_suites"
    )
    cases: Mapped[list["C2TestCase"]] = relationship(
        "C2TestCase",
        back_populates="suite_record",
        cascade="all, delete-orphan",
        order_by="C2TestCase.created_at",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "suite_id", name="uq_c2_suite_project_id_suite_id"
        ),
        Index("ix_c2_suite_lookup", "project_id", "suite_id"),
    )


class C2TestCase(Base):
    """Stores individual generated test definitions belonging to a suite."""

    __tablename__ = "c2_test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    suite_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c2_test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(
        String(32), default="live_agent", nullable=False
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    fixture_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Full GeneratedTestDefinition serialized as JSON
    definition: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    readiness: Mapped[str] = mapped_column(
        String(32), default="TEST_READY", nullable=False, index=True
    )
    readiness_reasons: Mapped[list] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    is_ready: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    suite_record: Mapped["C2TestSuite"] = relationship(
        "C2TestSuite", back_populates="cases"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "suite_id",
            "test_id",
            name="uq_c2_test_case_project_suite_test",
        ),
        Index("ix_c2_test_case_lookup", "project_id", "suite_id", "test_id"),
    )


class C2ExecutionEvidence(Base):
    """Stores retained runtime execution evidence, fixture snapshots, digests, and provenance."""

    __tablename__ = "c2_execution_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    runner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    runner_version: Mapped[str] = mapped_column(
        String(32), default="2026.1", nullable=False
    )

    execution_provenance: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "suite_id", "test_id", "run_id", name="uq_c2_execution_run"
        ),
        Index("ix_c2_execution_lookup", "project_id", "suite_id", "test_id", "run_id"),
    )


class C2EvaluationResult(Base):
    """Stores execution evaluation outcomes and first-divergence localisation records."""

    __tablename__ = "c2_evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    execution_evidence_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("c2_execution_evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    evaluator_version: Mapped[str] = mapped_column(
        String(32), default="c2_evaluator_v1", nullable=False
    )
    evaluator_config: Mapped[dict] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    evaluation_attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    reproduced_from_evaluation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    verdict: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reasons: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    violations: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    first_divergence: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    coverage: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    expected_states: Mapped[list] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    observed_states: Mapped[list] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    evidence_references: Mapped[list] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    evaluator_timing_ms: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "suite_id",
            "test_id",
            "run_id",
            "evaluator_version",
            "evaluation_attempt",
            name="uq_c2_evaluation_attempt",
        ),
        Index("ix_c2_evaluation_lookup", "project_id", "suite_id", "test_id"),
        Index("ix_c2_evaluation_verdict", "project_id", "verdict"),
    )
