"""C3-owned SQLAlchemy models for Phase 5 persistence.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class C3SuiteModel(Base):
    """C3-owned persisted frozen suite record."""

    __tablename__ = "c3_suites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suite_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    suite_digest: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)

    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    adapter_manifest_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    task_fixture_metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    recovery_contract_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    suite_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    cases: Mapped[list["C3CaseModel"]] = relationship(
        "C3CaseModel",
        back_populates="suite",
        cascade="all, delete-orphan",
        order_by="C3CaseModel.case_order",
    )


class C3CaseModel(Base):
    """C3-owned immutable candidate fault case snapshot within a frozen suite."""

    __tablename__ = "c3_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    suite_digest: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("c3_suites.suite_digest", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    case_fingerprint: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    case_family_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fault_family: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    effect_phase: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    interception_hook: Mapped[str] = mapped_column(String(64), nullable=False)
    target_tool_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_order: Mapped[int] = mapped_column(Integer, nullable=False)

    case_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    suite: Mapped[C3SuiteModel] = relationship("C3SuiteModel", back_populates="cases")

    __table_args__ = (
        UniqueConstraint(
            "suite_digest", "case_id", name="uq_c3_cases_suite_digest_case_id"
        ),
        Index("ix_c3_cases_project_suite", "project_id", "suite_digest"),
    )


class C3ExecutionModel(Base):
    """C3-owned suite execution lifecycle and progress record."""

    __tablename__ = "c3_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    suite_digest: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    suite_id: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_mode: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    caller_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    planned_cases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_cases_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    blocked_cases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsupported_cases_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    cancelled_cases_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    error_cases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    halt_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    started_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (Index("ix_c3_executions_project_status", "project_id", "status"),)


class C3MatchedPairModel(Base):
    """C3-owned matched trial pair evidence record linking clean control and fault trial."""

    __tablename__ = "c3_matched_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    case_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
        comment="Documented opaque reference to shared run record",
    )
    clean_trial_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fault_trial_id: Mapped[str] = mapped_column(String(128), nullable=False)

    readiness_status: Mapped[str] = mapped_column(String(32), nullable=False)
    clean_qualification: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    exposure_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exposure_assessed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cleanup_status: Mapped[str] = mapped_column(String(32), nullable=False)
    clean_execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    fault_execution_status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    evidence_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    evaluations: Mapped[list["C3EvaluationModel"]] = relationship(
        "C3EvaluationModel",
        back_populates="pair",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_c3_pairs_project_case", "project_id", "case_id"),
        Index("ix_c3_pairs_execution", "execution_id"),
    )


class C3EvaluationModel(Base):
    """C3-owned append-only recovery evaluation and rule outcomes record."""

    __tablename__ = "c3_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    pair_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("c3_matched_pairs.pair_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    evaluator_version: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    rule_set_version: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    evaluation_status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    recovery_verdict: Mapped[str | None] = mapped_column(
        String(32), index=True, nullable=True
    )
    first_violated_rule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_attribution: Mapped[str] = mapped_column(String(64), nullable=False)

    inputs_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Deterministic SHA-256 digest of matched evidence + C2 facts inputs",
    )

    c2_facts_provenance_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    rule_results_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    evaluation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    pair: Mapped[C3MatchedPairModel] = relationship(
        "C3MatchedPairModel", back_populates="evaluations"
    )

    __table_args__ = (
        UniqueConstraint(
            "pair_id",
            "evaluator_version",
            "rule_set_version",
            "inputs_digest",
            name="uq_c3_evaluations_idempotent_inputs",
        ),
        Index("ix_c3_eval_project_verdict", "project_id", "recovery_verdict"),
    )


class C3EvaluationReviewModel(Base):
    """Append-only human review of a stored recovery evaluation.

    The evaluation itself is never changed; reviewers record their own verdict next to it
    (the proposal's independent reviewer labels). Several reviews per evaluation are allowed.
    """

    __tablename__ = "c3_evaluation_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    evaluation_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("c3_evaluations.evaluation_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pair_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    evaluator_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
