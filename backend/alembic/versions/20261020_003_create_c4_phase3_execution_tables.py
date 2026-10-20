"""Create C4 Phase 3 execution runs table

Revision ID: 20261020_003_c4
Revises: 20261019_002_c4
Create Date: 2026-10-20 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_003_c4"
down_revision: str | Sequence[str] | None = "20261019_002_c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "c4_execution_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False),
        sa.Column("adapter_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_version", sa.String(length=64), nullable=False),
        sa.Column("adapter_config_digest", sa.String(length=64), nullable=False),
        sa.Column("execution_mode", sa.String(length=64), nullable=False),
        sa.Column("simulated_behavior", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("exposure_status", sa.String(length=64), nullable=False),
        sa.Column("policy_verdict", sa.String(length=32), nullable=False),
        sa.Column("attacker_objective_outcome", sa.String(length=64), nullable=False),
        sa.Column("task_utility_outcome", sa.String(length=64), nullable=False),
        sa.Column("cleanup_status", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("run_data", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_c4_execution_runs_run_id"),
    )
    op.create_index(
        op.f("ix_c4_execution_runs_project_id"),
        "c4_execution_runs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_execution_runs_case_id"),
        "c4_execution_runs",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_execution_runs_run_id"),
        "c4_execution_runs",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_execution_runs_idempotency_key"),
        "c4_execution_runs",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_c4_execution_runs_idempotency_key"), table_name="c4_execution_runs")
    op.drop_index(op.f("ix_c4_execution_runs_run_id"), table_name="c4_execution_runs")
    op.drop_index(op.f("ix_c4_execution_runs_case_id"), table_name="c4_execution_runs")
    op.drop_index(op.f("ix_c4_execution_runs_project_id"), table_name="c4_execution_runs")
    op.drop_table("c4_execution_runs")
