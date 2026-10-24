"""Additive repair migration for missing component schemas.

Revision ID: 20261024_repair_missing_component_schemas
Revises: 20261024_user_model_selections
Create Date: 2026-10-24 11:30:00.000000

Component: Additive schema repair for C1, C2, and C3 missing tables and columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20261024_002_repair_schemas"
down_revision: str | Sequence[str] | None = "20261024_user_model_selections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    if context.is_offline_mode():
        existing_tables = set()
    else:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # 1. C1 TABLES
    # =========================================================================

    # 1.1 c1_project_configs
    if "c1_project_configs" not in existing_tables:
        op.create_table(
            "c1_project_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "is_immutable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("agent_connection_ref", sa.String(length=255), nullable=False),
            sa.Column("tools", sa.JSON(), nullable=False),
            sa.Column("requirements", sa.JSON(), nullable=False),
            sa.Column("tool_constraints", sa.JSON(), nullable=False),
            sa.Column("expectations", sa.JSON(), nullable=False),
            sa.Column("synthetic_fixture_refs", sa.JSON(), nullable=False),
            sa.Column("reset_capability", sa.JSON(), nullable=True),
            sa.Column("trace_capabilities", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id", "version", name="uq_c1_project_config_version"
            ),
        )
        op.create_index(
            op.f("ix_c1_project_configs_project_id"),
            "c1_project_configs",
            ["project_id"],
            unique=False,
        )

    # 1.2 c1_suite_versions
    if "c1_suite_versions" not in existing_tables:
        op.create_table(
            "c1_suite_versions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("suite_id", sa.String(length=100), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("config_id", sa.String(length=36), nullable=False),
            sa.Column(
                "is_immutable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("cases", sa.JSON(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("generation_run_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["config_id"], ["c1_project_configs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id", "suite_id", "version", name="uq_c1_suite_version"
            ),
        )
        op.create_index(
            op.f("ix_c1_suite_versions_project_id"),
            "c1_suite_versions",
            ["project_id"],
            unique=False,
        )

    # 1.3 c1_generation_runs
    if "c1_generation_runs" not in existing_tables:
        op.create_table(
            "c1_generation_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("config_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("candidates", sa.JSON(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("suite_id", sa.String(length=100), nullable=True),
            sa.Column("suite_version_id", sa.String(length=36), nullable=True),
            sa.Column("error_message", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["config_id"], ["c1_project_configs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_c1_generation_runs_project_id"),
            "c1_generation_runs",
            ["project_id"],
            unique=False,
        )

    # 1.4 c1_execution_runs
    if "c1_execution_runs" not in existing_tables:
        op.create_table(
            "c1_execution_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("suite_id", sa.String(length=100), nullable=False),
            sa.Column("suite_version", sa.Integer(), nullable=False),
            sa.Column("suite_version_id", sa.String(length=36), nullable=False),
            sa.Column("config_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
            sa.Column("effective_config", sa.JSON(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["config_id"], ["c1_project_configs.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["suite_version_id"], ["c1_suite_versions.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_c1_execution_runs_project_id"),
            "c1_execution_runs",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_execution_runs_idempotency_key"),
            "c1_execution_runs",
            ["idempotency_key"],
            unique=False,
        )

    # 1.5 c1_case_executions
    if "c1_case_executions" not in existing_tables:
        op.create_table(
            "c1_case_executions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("case_id", sa.String(length=100), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=False),
            sa.Column("readiness_status", sa.String(length=50), nullable=False),
            sa.Column("execution_status", sa.String(length=50), nullable=False),
            sa.Column("verdict", sa.String(length=50), nullable=True),
            sa.Column("trace_completeness", sa.String(length=50), nullable=False),
            sa.Column("resolved_expectations", sa.JSON(), nullable=False),
            sa.Column("agent_task_sent", sa.JSON(), nullable=True),
            sa.Column("captured_events", sa.JSON(), nullable=False),
            sa.Column("evidence_records", sa.JSON(), nullable=False),
            sa.Column("raw_trace", sa.JSON(), nullable=False),
            sa.Column("check_results", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["run_id"], ["c1_execution_runs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "run_id", "case_id", "attempt_number", name="uq_c1_case_execution_attempt"
            ),
        )
        op.create_index(
            op.f("ix_c1_case_executions_run_id"),
            "c1_case_executions",
            ["run_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_executions_case_id"),
            "c1_case_executions",
            ["case_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_executions_verdict"),
            "c1_case_executions",
            ["verdict"],
            unique=False,
        )

    # 1.6 c1_case_diagnoses
    if "c1_case_diagnoses" not in existing_tables:
        op.create_table(
            "c1_case_diagnoses",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("case_execution_id", sa.String(length=36), nullable=False),
            sa.Column("case_id", sa.String(length=100), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "requirement_version",
                sa.String(length=50),
                nullable=False,
                server_default="v1.0",
            ),
            sa.Column(
                "evaluator_version",
                sa.String(length=50),
                nullable=False,
                server_default="c1-evaluator-v1.0",
            ),
            sa.Column(
                "explanation_version",
                sa.String(length=50),
                nullable=False,
                server_default="c1-diagnosis-v1.0",
            ),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default="COMPLETED",
            ),
            sa.Column("cause_category", sa.String(length=50), nullable=False),
            sa.Column("explanation_summary", sa.String(length=2000), nullable=False),
            sa.Column("check_explanations", sa.JSON(), nullable=False),
            sa.Column("candidate_code_locations", sa.JSON(), nullable=False),
            sa.Column("evidence_refs", sa.JSON(), nullable=False),
            sa.Column("source_hash", sa.String(length=64), nullable=True),
            sa.Column(
                "explanation_method",
                sa.String(length=50),
                nullable=False,
                server_default="DETERMINISTIC_RULE_DERIVATION",
            ),
            sa.Column("metrics", sa.JSON(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["case_execution_id"], ["c1_case_executions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["c1_execution_runs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "run_id",
                "case_id",
                "attempt_number",
                "explanation_version",
                name="uq_c1_case_diagnosis_attempt",
            ),
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_project_id"),
            "c1_case_diagnoses",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_run_id"),
            "c1_case_diagnoses",
            ["run_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_case_execution_id"),
            "c1_case_diagnoses",
            ["case_execution_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_case_id"),
            "c1_case_diagnoses",
            ["case_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_cause_category"),
            "c1_case_diagnoses",
            ["cause_category"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_case_diagnoses_idempotency_key"),
            "c1_case_diagnoses",
            ["idempotency_key"],
            unique=False,
        )

    # 1.7 c1_corrections
    if "c1_corrections" not in existing_tables:
        op.create_table(
            "c1_corrections",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("case_execution_id", sa.String(length=36), nullable=False),
            sa.Column("case_id", sa.String(length=100), nullable=False),
            sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source_hash", sa.String(length=64), nullable=True),
            sa.Column("source_commit", sa.String(length=64), nullable=True),
            sa.Column("permitted_paths", sa.JSON(), nullable=False),
            sa.Column("candidate_patch", sa.JSON(), nullable=True),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default="PENDING",
            ),
            sa.Column(
                "is_verified",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("ineligibility_reasons", sa.JSON(), nullable=False),
            sa.Column("verification_results", sa.JSON(), nullable=False),
            sa.Column("review", sa.JSON(), nullable=False),
            sa.Column(
                "isolation_type",
                sa.String(length=50),
                nullable=False,
                server_default="DISPOSABLE_SUBPROCESS",
            ),
            sa.Column("metrics", sa.JSON(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["case_execution_id"], ["c1_case_executions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["diagnosis_id"], ["c1_case_diagnoses.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["c1_execution_runs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "run_id",
                "case_id",
                "attempt_number",
                name="uq_c1_correction_attempt",
            ),
        )
        op.create_index(
            op.f("ix_c1_corrections_project_id"),
            "c1_corrections",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_run_id"),
            "c1_corrections",
            ["run_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_case_execution_id"),
            "c1_corrections",
            ["case_execution_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_case_id"),
            "c1_corrections",
            ["case_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_diagnosis_id"),
            "c1_corrections",
            ["diagnosis_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_status"),
            "c1_corrections",
            ["status"],
            unique=False,
        )
        op.create_index(
            op.f("ix_c1_corrections_idempotency_key"),
            "c1_corrections",
            ["idempotency_key"],
            unique=False,
        )

    # 1.8 c1_reference_labels
    if "c1_reference_labels" not in existing_tables:
        op.create_table(
            "c1_reference_labels",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=100), nullable=False),
            sa.Column("case_id", sa.String(length=100), nullable=False),
            sa.Column("suite_id", sa.String(length=100), nullable=True),
            sa.Column("task_family", sa.String(length=100), nullable=False),
            sa.Column("dataset_split", sa.String(length=50), nullable=False),
            sa.Column("ground_truth_verdict", sa.String(length=50), nullable=False),
            sa.Column("ground_truth_cause", sa.String(length=50), nullable=True),
            sa.Column("ground_truth_code_locations", sa.JSON(), nullable=False),
            sa.Column("valid_evidence_refs", sa.JSON(), nullable=False),
            sa.Column("reviewer_id", sa.String(length=100), nullable=False),
            sa.Column("label_version", sa.String(length=50), nullable=False),
            sa.Column("disagreements", sa.JSON(), nullable=False),
            sa.Column("adjudication", sa.JSON(), nullable=False),
            sa.Column(
                "is_held_out",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id",
                "case_id",
                "label_version",
                name="uq_c1_reference_label_version",
            ),
        )
        op.create_index(
            "ix_c1_reference_labels_project_id",
            "c1_reference_labels",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c1_reference_labels_case_id",
            "c1_reference_labels",
            ["case_id"],
            unique=False,
        )
        op.create_index(
            "ix_c1_reference_labels_task_family",
            "c1_reference_labels",
            ["task_family"],
            unique=False,
        )
        op.create_index(
            "ix_c1_reference_labels_dataset_split",
            "c1_reference_labels",
            ["dataset_split"],
            unique=False,
        )

    # =========================================================================
    # 2. C2 TABLES & COLUMNS
    # =========================================================================

    # 2.1 c2_execution_evidence
    if "c2_execution_evidence" not in existing_tables:
        op.create_table(
            "c2_execution_evidence",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("suite_id", sa.String(length=64), nullable=False),
            sa.Column("test_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("evidence_digest", sa.String(length=64), nullable=False),
            sa.Column("model_id", sa.String(length=64), nullable=False),
            sa.Column("model_version", sa.String(length=32), nullable=False),
            sa.Column("model_content_hash", sa.String(length=64), nullable=False),
            sa.Column("execution_mode", sa.String(length=32), nullable=False),
            sa.Column("runner_id", sa.String(length=64), nullable=False),
            sa.Column(
                "runner_version",
                sa.String(length=32),
                server_default="2026.1",
                nullable=False,
            ),
            sa.Column("execution_provenance", json_type, nullable=False),
            sa.Column("evidence_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id",
                "suite_id",
                "test_id",
                "run_id",
                name="uq_c2_execution_run",
            ),
        )
        op.create_index(
            "ix_c2_execution_evidence_project_id",
            "c2_execution_evidence",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_execution_evidence_suite_id",
            "c2_execution_evidence",
            ["suite_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_execution_evidence_test_id",
            "c2_execution_evidence",
            ["test_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_execution_evidence_run_id",
            "c2_execution_evidence",
            ["run_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_execution_evidence_digest",
            "c2_execution_evidence",
            ["evidence_digest"],
            unique=False,
        )
        op.create_index(
            "ix_c2_execution_lookup",
            "c2_execution_evidence",
            ["project_id", "suite_id", "test_id", "run_id"],
            unique=False,
        )

    # 2.2 c2_experiment_datasets
    if "c2_experiment_datasets" not in existing_tables:
        op.create_table(
            "c2_experiment_datasets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("dataset_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_frozen", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("frozen_at", sa.DateTime(), nullable=True),
            sa.Column("manifest_digest", sa.String(length=64), nullable=False),
            sa.Column("case_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column(
                "development_count", sa.Integer(), server_default="0", nullable=False
            ),
            sa.Column("held_out_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("manifest_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id",
                "dataset_id",
                "version",
                name="uq_c2_dataset_project_id_version",
            ),
        )
        op.create_index(
            "ix_c2_experiment_datasets_project_id",
            "c2_experiment_datasets",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_datasets_dataset_id",
            "c2_experiment_datasets",
            ["dataset_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_datasets_version",
            "c2_experiment_datasets",
            ["version"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_datasets_manifest_digest",
            "c2_experiment_datasets",
            ["manifest_digest"],
            unique=False,
        )
        op.create_index(
            "ix_c2_dataset_lookup",
            "c2_experiment_datasets",
            ["project_id", "dataset_id", "version"],
            unique=False,
        )

    # 2.3 c2_experiments
    if "c2_experiments" not in existing_tables:
        op.create_table(
            "c2_experiments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("experiment_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("dataset_record_id", sa.String(length=36), nullable=False),
            sa.Column("dataset_id", sa.String(length=64), nullable=False),
            sa.Column("dataset_version", sa.String(length=32), nullable=False),
            sa.Column(
                "status", sa.String(length=32), server_default="PENDING", nullable=False
            ),
            sa.Column("configuration", json_type, nullable=False),
            sa.Column("results_summary", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["dataset_record_id"],
                ["c2_experiment_datasets.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id", "experiment_id", name="uq_c2_experiment_project_id"
            ),
        )
        op.create_index(
            "ix_c2_experiments_project_id",
            "c2_experiments",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiments_experiment_id",
            "c2_experiments",
            ["experiment_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiments_dataset_record_id",
            "c2_experiments",
            ["dataset_record_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiments_dataset_id",
            "c2_experiments",
            ["dataset_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiments_status",
            "c2_experiments",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_lookup",
            "c2_experiments",
            ["project_id", "experiment_id"],
            unique=False,
        )

    # 2.4 c2_experiment_case_results
    if "c2_experiment_case_results" not in existing_tables:
        op.create_table(
            "c2_experiment_case_results",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("experiment_record_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("experiment_id", sa.String(length=64), nullable=False),
            sa.Column("case_id", sa.String(length=64), nullable=False),
            sa.Column("method_id", sa.String(length=32), nullable=False),
            sa.Column("partition", sa.String(length=32), nullable=False),
            sa.Column("verdict", sa.String(length=32), nullable=False),
            sa.Column("is_violation", sa.Boolean(), nullable=False),
            sa.Column(
                "can_localize", sa.Boolean(), server_default="false", nullable=False
            ),
            sa.Column("first_divergence_predicted_step", sa.Integer(), nullable=True),
            sa.Column("first_divergence_event_id", sa.String(length=64), nullable=True),
            sa.Column(
                "evaluator_timing_ms", sa.Float(), server_default="0.0", nullable=False
            ),
            sa.Column("source_evidence_digest", sa.String(length=64), nullable=True),
            sa.Column("evidence_digest_consumed", sa.String(length=64), nullable=False),
            sa.Column(
                "is_excluded", sa.Boolean(), server_default="false", nullable=False
            ),
            sa.Column("exclusion_reason", sa.String(length=256), nullable=True),
            sa.Column("result_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["experiment_record_id"],
                ["c2_experiments.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "experiment_record_id",
                "case_id",
                "method_id",
                name="uq_c2_exp_case_method",
            ),
        )
        op.create_index(
            "ix_c2_experiment_case_results_experiment_record_id",
            "c2_experiment_case_results",
            ["experiment_record_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_case_results_project_id",
            "c2_experiment_case_results",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_case_results_experiment_id",
            "c2_experiment_case_results",
            ["experiment_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_case_results_case_id",
            "c2_experiment_case_results",
            ["case_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_case_results_method_id",
            "c2_experiment_case_results",
            ["method_id"],
            unique=False,
        )
        op.create_index(
            "ix_c2_experiment_case_results_partition",
            "c2_experiment_case_results",
            ["partition"],
            unique=False,
        )

    # 2.5 c2_evaluation_results missing columns
    if "c2_evaluation_results" in existing_tables:
        existing_cols = {
            col["name"] for col in inspector.get_columns("c2_evaluation_results")
        }
        with op.batch_alter_table("c2_evaluation_results", schema=None) as batch_op:
            if "execution_evidence_id" not in existing_cols:
                batch_op.add_column(
                    sa.Column(
                        "execution_evidence_id",
                        sa.String(length=36),
                        nullable=True,
                    )
                )
            if "evaluator_config" not in existing_cols:
                batch_op.add_column(
                    sa.Column(
                        "evaluator_config",
                        json_type,
                        server_default=sa.text("'{}'"),
                        nullable=False,
                    )
                )
            if "evaluation_attempt" not in existing_cols:
                batch_op.add_column(
                    sa.Column(
                        "evaluation_attempt",
                        sa.Integer(),
                        server_default=sa.text("1"),
                        nullable=False,
                    )
                )
            if "evidence_digest" not in existing_cols:
                batch_op.add_column(
                    sa.Column(
                        "evidence_digest",
                        sa.String(length=64),
                        nullable=True,
                    )
                )
            if "reproduced_from_evaluation_id" not in existing_cols:
                batch_op.add_column(
                    sa.Column(
                        "reproduced_from_evaluation_id",
                        sa.String(length=36),
                        nullable=True,
                    )
                )

        existing_c2_eval_indexes = {
            idx["name"] for idx in inspector.get_indexes("c2_evaluation_results")
        }
        if (
            "ix_c2_evaluation_results_evidence_digest"
            not in existing_c2_eval_indexes
        ):
            op.create_index(
                "ix_c2_evaluation_results_evidence_digest",
                "c2_evaluation_results",
                ["evidence_digest"],
                unique=False,
            )

    # =========================================================================
    # 3. C3 TABLES
    # =========================================================================

    # 3.1 c3_suites
    if "c3_suites" not in existing_tables:
        op.create_table(
            "c3_suites",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("suite_id", sa.String(length=128), nullable=False),
            sa.Column("suite_digest", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column("task_id", sa.String(length=128), nullable=False),
            sa.Column("tool_id", sa.String(length=128), nullable=False),
            sa.Column("domain", sa.String(length=64), nullable=False),
            sa.Column("schema_version", sa.String(length=32), nullable=False),
            sa.Column("generator_version", sa.String(length=32), nullable=False),
            sa.Column("total_cases", sa.Integer(), nullable=False),
            sa.Column("policy_snapshot", sa.JSON(), nullable=False),
            sa.Column("adapter_manifest_snapshot", sa.JSON(), nullable=False),
            sa.Column("task_fixture_metadata_snapshot", sa.JSON(), nullable=False),
            sa.Column("recovery_contract_snapshot", sa.JSON(), nullable=False),
            sa.Column("suite_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("suite_digest", name="uq_c3_suites_suite_digest"),
        )
        op.create_index("ix_c3_suites_suite_id", "c3_suites", ["suite_id"], unique=False)
        op.create_index(
            "ix_c3_suites_suite_digest", "c3_suites", ["suite_digest"], unique=True
        )
        op.create_index(
            "ix_c3_suites_project_id", "c3_suites", ["project_id"], unique=False
        )

    # 3.2 c3_cases
    if "c3_cases" not in existing_tables:
        op.create_table(
            "c3_cases",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("case_id", sa.String(length=128), nullable=False),
            sa.Column("suite_digest", sa.String(length=64), nullable=False),
            sa.Column("case_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("content_digest", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column("case_family_id", sa.String(length=128), nullable=False),
            sa.Column("fault_family", sa.String(length=64), nullable=False),
            sa.Column("effect_phase", sa.String(length=64), nullable=False),
            sa.Column("interception_hook", sa.String(length=64), nullable=False),
            sa.Column("target_tool_id", sa.String(length=128), nullable=False),
            sa.Column("case_order", sa.Integer(), nullable=False),
            sa.Column("case_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["suite_digest"], ["c3_suites.suite_digest"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "suite_digest", "case_id", name="uq_c3_cases_suite_digest_case_id"
            ),
        )
        op.create_index("ix_c3_cases_case_id", "c3_cases", ["case_id"], unique=False)
        op.create_index(
            "ix_c3_cases_suite_digest", "c3_cases", ["suite_digest"], unique=False
        )
        op.create_index(
            "ix_c3_cases_case_fingerprint", "c3_cases", ["case_fingerprint"], unique=False
        )
        op.create_index("ix_c3_cases_project_id", "c3_cases", ["project_id"], unique=False)
        op.create_index(
            "ix_c3_cases_fault_family", "c3_cases", ["fault_family"], unique=False
        )
        op.create_index(
            "ix_c3_cases_effect_phase", "c3_cases", ["effect_phase"], unique=False
        )
        op.create_index(
            "ix_c3_cases_project_suite",
            "c3_cases",
            ["project_id", "suite_digest"],
            unique=False,
        )

    # 3.3 c3_executions
    if "c3_executions" not in existing_tables:
        op.create_table(
            "c3_executions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("execution_id", sa.String(length=128), nullable=False),
            sa.Column("suite_digest", sa.String(length=64), nullable=False),
            sa.Column("suite_id", sa.String(length=128), nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column("target_mode", sa.String(length=32), nullable=False),
            sa.Column("caller_identity", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "planned_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "executed_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "blocked_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "unsupported_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "cancelled_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "error_cases_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("halt_reason", sa.Text(), nullable=True),
            sa.Column("manifest_snapshot", sa.JSON(), nullable=False),
            sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("execution_id", name="uq_c3_executions_execution_id"),
        )
        op.create_index(
            "ix_c3_executions_execution_id",
            "c3_executions",
            ["execution_id"],
            unique=True,
        )
        op.create_index(
            "ix_c3_executions_suite_digest",
            "c3_executions",
            ["suite_digest"],
            unique=False,
        )
        op.create_index(
            "ix_c3_executions_project_id", "c3_executions", ["project_id"], unique=False
        )
        op.create_index(
            "ix_c3_executions_target_mode", "c3_executions", ["target_mode"], unique=False
        )
        op.create_index(
            "ix_c3_executions_status", "c3_executions", ["status"], unique=False
        )
        op.create_index(
            "ix_c3_executions_project_status",
            "c3_executions",
            ["project_id", "status"],
            unique=False,
        )

    # 3.4 c3_matched_pairs
    if "c3_matched_pairs" not in existing_tables:
        op.create_table(
            "c3_matched_pairs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pair_id", sa.String(length=128), nullable=False),
            sa.Column("execution_id", sa.String(length=128), nullable=True),
            sa.Column("case_id", sa.String(length=128), nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column(
                "run_id",
                sa.String(length=128),
                nullable=False,
                comment="Documented opaque reference to shared run record",
            ),
            sa.Column("clean_trial_id", sa.String(length=128), nullable=False),
            sa.Column("fault_trial_id", sa.String(length=128), nullable=False),
            sa.Column("readiness_status", sa.String(length=32), nullable=False),
            sa.Column("clean_qualification", sa.String(length=32), nullable=False),
            sa.Column("exposure_status", sa.String(length=32), nullable=False),
            sa.Column("exposure_assessed", sa.Boolean(), nullable=False),
            sa.Column("cleanup_status", sa.String(length=32), nullable=False),
            sa.Column("clean_execution_status", sa.String(length=32), nullable=False),
            sa.Column("fault_execution_status", sa.String(length=32), nullable=False),
            sa.Column("evidence_complete", sa.Boolean(), nullable=False),
            sa.Column("evidence_digest", sa.String(length=64), nullable=False),
            sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("pair_id", name="uq_c3_matched_pairs_pair_id"),
        )
        op.create_index(
            "ix_c3_matched_pairs_pair_id", "c3_matched_pairs", ["pair_id"], unique=True
        )
        op.create_index(
            "ix_c3_matched_pairs_execution_id",
            "c3_matched_pairs",
            ["execution_id"],
            unique=False,
        )
        op.create_index(
            "ix_c3_matched_pairs_case_id", "c3_matched_pairs", ["case_id"], unique=False
        )
        op.create_index(
            "ix_c3_matched_pairs_project_id",
            "c3_matched_pairs",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            "ix_c3_matched_pairs_run_id", "c3_matched_pairs", ["run_id"], unique=False
        )
        op.create_index(
            "ix_c3_matched_pairs_clean_qualification",
            "c3_matched_pairs",
            ["clean_qualification"],
            unique=False,
        )
        op.create_index(
            "ix_c3_matched_pairs_exposure_status",
            "c3_matched_pairs",
            ["exposure_status"],
            unique=False,
        )
        op.create_index(
            "ix_c3_matched_pairs_fault_execution_status",
            "c3_matched_pairs",
            ["fault_execution_status"],
            unique=False,
        )
        op.create_index(
            "ix_c3_pairs_project_case",
            "c3_matched_pairs",
            ["project_id", "case_id"],
            unique=False,
        )
        op.create_index(
            "ix_c3_pairs_execution", "c3_matched_pairs", ["execution_id"], unique=False
        )

    # 3.5 c3_evaluations
    if "c3_evaluations" not in existing_tables:
        op.create_table(
            "c3_evaluations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("evaluation_id", sa.String(length=128), nullable=False),
            sa.Column("pair_id", sa.String(length=128), nullable=False),
            sa.Column("case_id", sa.String(length=128), nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column("evaluator_version", sa.String(length=32), nullable=False),
            sa.Column("rule_set_version", sa.String(length=32), nullable=False),
            sa.Column("evaluation_status", sa.String(length=32), nullable=False),
            sa.Column("recovery_verdict", sa.String(length=32), nullable=True),
            sa.Column("first_violated_rule", sa.String(length=64), nullable=True),
            sa.Column("actor_attribution", sa.String(length=64), nullable=False),
            sa.Column(
                "inputs_digest",
                sa.String(length=64),
                nullable=False,
                comment="Deterministic SHA-256 digest of matched evidence + C2 facts inputs",
            ),
            sa.Column("c2_facts_provenance_snapshot", sa.JSON(), nullable=False),
            sa.Column("rule_results_snapshot", sa.JSON(), nullable=False),
            sa.Column("evaluation_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["pair_id"], ["c3_matched_pairs.pair_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("evaluation_id", name="uq_c3_evaluations_evaluation_id"),
            sa.UniqueConstraint(
                "pair_id",
                "evaluator_version",
                "rule_set_version",
                "inputs_digest",
                name="uq_c3_evaluations_idempotent_inputs",
            ),
        )
        op.create_index(
            "ix_c3_evaluations_evaluation_id",
            "c3_evaluations",
            ["evaluation_id"],
            unique=True,
        )
        op.create_index(
            "ix_c3_evaluations_pair_id", "c3_evaluations", ["pair_id"], unique=False
        )
        op.create_index(
            "ix_c3_evaluations_case_id", "c3_evaluations", ["case_id"], unique=False
        )
        op.create_index(
            "ix_c3_evaluations_project_id", "c3_evaluations", ["project_id"], unique=False
        )
        op.create_index(
            "ix_c3_evaluations_evaluator_version",
            "c3_evaluations",
            ["evaluator_version"],
            unique=False,
        )
        op.create_index(
            "ix_c3_evaluations_rule_set_version",
            "c3_evaluations",
            ["rule_set_version"],
            unique=False,
        )
        op.create_index(
            "ix_c3_evaluations_evaluation_status",
            "c3_evaluations",
            ["evaluation_status"],
            unique=False,
        )
        op.create_index(
            "ix_c3_evaluations_recovery_verdict",
            "c3_evaluations",
            ["recovery_verdict"],
            unique=False,
        )
        op.create_index(
            "ix_c3_eval_project_verdict",
            "c3_evaluations",
            ["project_id", "recovery_verdict"],
            unique=False,
        )


def downgrade() -> None:
    # Downgrade drops repair objects safely in reverse dependency order
    if context.is_offline_mode():
        existing_tables = set()
    else:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        existing_tables = set(inspector.get_table_names())

    # C3 drops
    for table_name in [
        "c3_evaluations",
        "c3_matched_pairs",
        "c3_executions",
        "c3_cases",
        "c3_suites",
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)

    # C2 drops
    for table_name in [
        "c2_experiment_case_results",
        "c2_experiments",
        "c2_experiment_datasets",
        "c2_execution_evidence",
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)

    # C1 drops
    for table_name in [
        "c1_reference_labels",
        "c1_corrections",
        "c1_case_diagnoses",
        "c1_case_executions",
        "c1_execution_runs",
        "c1_generation_runs",
        "c1_suite_versions",
        "c1_project_configs",
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)
