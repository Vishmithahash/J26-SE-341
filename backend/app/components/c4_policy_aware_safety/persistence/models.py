from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class C4ArtifactModel(Base):
    """SQLAlchemy model for versioned C4 policy artifacts."""

    __tablename__ = "c4_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    meta_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "artifact_id", "version", name="uq_c4_artifacts_proj_id_ver"
        ),
    )


class C4CandidateRuleModel(Base):
    """SQLAlchemy model for candidate and imported policy rules."""

    __tablename__ = "c4_candidate_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_family: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    rule_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    validation_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "rule_id",
            "rule_version",
            name="uq_c4_candidate_rules_proj_id_ver",
        ),
    )


class C4ContractModel(Base):
    """SQLAlchemy model for versioned policy contracts."""

    __tablename__ = "c4_policy_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_data: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    referenced_artifact_versions: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    acceptance_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "contract_id", "version", name="uq_c4_contracts_proj_id_ver"
        ),
    )


class C4FindingModel(Base):
    """SQLAlchemy model for persisted evaluation findings."""

    __tablename__ = "c4_evaluation_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    violation_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finding_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class C4DomainBindingModel(Base):
    """SQLAlchemy model for versioned domain and application bindings."""

    __tablename__ = "c4_domain_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    binding_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "binding_id",
            "version",
            name="uq_c4_domain_bindings_proj_id_ver",
        ),
    )


class C4GenerationBatchModel(Base):
    """SQLAlchemy model for test case generation batches and reports."""

    __tablename__ = "c4_generation_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binding_version: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    report_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class C4TestCaseModel(Base):
    """SQLAlchemy model for versioned and frozen policy test cases."""

    __tablename__ = "c4_test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    project_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    test_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    case_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    frozen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "case_id",
            "case_version",
            name="uq_c4_test_cases_proj_id_ver",
        ),
    )
