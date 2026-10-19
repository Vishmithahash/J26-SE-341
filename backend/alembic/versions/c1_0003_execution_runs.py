"""Create C1 execution runs and case executions tables

Revision ID: c1_0003
Revises: c1_0002
Create Date: 2026-10-19 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0003"
down_revision: str | None = "c1_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(
        op.f("ix_c1_case_executions_verdict"), table_name="c1_case_executions"
    )
    op.drop_index(
        op.f("ix_c1_case_executions_case_id"), table_name="c1_case_executions"
    )
    op.drop_index(op.f("ix_c1_case_executions_run_id"), table_name="c1_case_executions")
    op.drop_table("c1_case_executions")

    op.drop_index(
        op.f("ix_c1_execution_runs_idempotency_key"), table_name="c1_execution_runs"
    )
    op.drop_index(
        op.f("ix_c1_execution_runs_project_id"), table_name="c1_execution_runs"
    )
    op.drop_table("c1_execution_runs")
