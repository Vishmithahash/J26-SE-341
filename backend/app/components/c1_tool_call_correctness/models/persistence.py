import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class C1ProjectConfigModel(Base):
    """Persisted Component 1 project configuration version and tool/requirement snapshot."""

    __tablename__ = "c1_project_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    agent_connection_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tool_constraints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expectations: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synthetic_fixture_refs: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    reset_capability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    suite_versions = relationship(
        "C1SuiteVersionModel",
        back_populates="config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    generation_runs = relationship(
        "C1GenerationRunModel",
        back_populates="config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    execution_runs = relationship(
        "C1ExecutionRunModel",
        back_populates="config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_c1_project_config_version"),
    )


class C1SuiteVersionModel(Base):
    """Accepted and immutable collection of test cases bound to a configuration snapshot."""

    __tablename__ = "c1_suite_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_project_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    config = relationship("C1ProjectConfigModel", back_populates="suite_versions")
    execution_runs = relationship(
        "C1ExecutionRunModel",
        back_populates="suite_version_rel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "suite_id", "version", name="uq_c1_suite_version"
        ),
    )


class C1GenerationRunModel(Base):
    """Persisted generation run tracking candidate cases, validation results, and selection provenance."""

    __tablename__ = "c1_generation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_project_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    candidates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    suite_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suite_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    config = relationship("C1ProjectConfigModel", back_populates="generation_runs")


class C1ExecutionRunModel(Base):
    """Persisted test execution run for an accepted suite version."""

    __tablename__ = "c1_execution_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(100), nullable=False)
    suite_version: Mapped[int] = mapped_column(Integer, nullable=False)
    suite_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_suite_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_project_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    effective_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    config = relationship("C1ProjectConfigModel", back_populates="execution_runs")
    suite_version_rel = relationship(
        "C1SuiteVersionModel", back_populates="execution_runs"
    )
    case_executions = relationship(
        "C1CaseExecutionModel",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    diagnoses = relationship(
        "C1CaseDiagnosisModel",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class C1CaseExecutionModel(Base):
    """Execution record and evaluation result for a single test case within a run."""

    __tablename__ = "c1_case_executions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    trace_completeness: Mapped[str] = mapped_column(
        String(50), nullable=False, default="COMPLETE"
    )
    resolved_expectations: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    agent_task_sent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    captured_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_records: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_trace: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    check_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    run = relationship("C1ExecutionRunModel", back_populates="case_executions")
    diagnoses = relationship(
        "C1CaseDiagnosisModel",
        back_populates="case_execution",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "case_id",
            "attempt_number",
            name="uq_c1_case_execution_attempt",
        ),
    )


class C1CaseDiagnosisModel(Base):
    """Persisted diagnosis and evidence-linked explanation for a case execution."""

    __tablename__ = "c1_case_diagnoses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_case_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requirement_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="v1.0"
    )
    evaluator_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="c1-evaluator-v1.0"
    )
    explanation_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="c1-diagnosis-v1.0"
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")
    cause_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    explanation_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    check_explanations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_code_locations: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    explanation_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DETERMINISTIC_RULE_DERIVATION"
    )
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    run = relationship("C1ExecutionRunModel", back_populates="diagnoses")
    case_execution = relationship("C1CaseExecutionModel", back_populates="diagnoses")

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "case_id",
            "attempt_number",
            "explanation_version",
            name="uq_c1_case_diagnosis_attempt",
        ),
    )


class C1CorrectionModel(Base):
    """Persisted correction attempt, sandbox verification results, and developer decision."""

    __tablename__ = "c1_corrections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_case_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_case_diagnoses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permitted_paths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_patch: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING", index=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ineligibility_reasons: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    verification_results: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    review: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    isolation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DISPOSABLE_SUBPROCESS"
    )
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "case_id",
            "attempt_number",
            name="uq_c1_correction_attempt",
        ),
    )


class C1ReferenceLabelModel(Base):
    """Independently reviewed ground truth labels and benchmark splits for research evaluation."""

    __tablename__ = "c1_reference_labels"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    suite_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_family: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dataset_split: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ground_truth_verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    ground_truth_cause: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ground_truth_code_locations: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    valid_evidence_refs: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    label_version: Mapped[str] = mapped_column(String(50), nullable=False)
    disagreements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    adjudication: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_held_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "case_id",
            "label_version",
            name="uq_c1_reference_label_version",
        ),
    )
