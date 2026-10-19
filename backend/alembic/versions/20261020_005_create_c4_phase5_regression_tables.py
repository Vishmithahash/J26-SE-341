"""Create C4 Phase 5 regression tables and idempotency constraint

Revision ID: 20261020_005_c4
Revises: 20261020_004_c4
Create Date: 2026-10-20 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_005_c4"
down_revision: str | Sequence[str] | None = "20261020_004_c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add database-enforced project-scoped idempotency constraint on c4_execution_runs
    op.create_unique_constraint(
        "uq_c4_execution_runs_proj_idempotency",
        "c4_execution_runs",
        ["project_id", "idempotency_key"],
    )

    # 2. Create c4_policy_comparisons table
    op.create_table(
        "c4_policy_comparisons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comparison_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("baseline_contract_id", sa.String(length=128), nullable=False),
        sa.Column("baseline_contract_version", sa.Integer(), nullable=False),
        sa.Column("candidate_contract_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_contract_version", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("configuration_digest", sa.String(length=64), nullable=False),
        sa.Column("comparison_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comparison_id"),
    )
    op.create_index(
        "ix_c4_policy_comparisons_project_id",
        "c4_policy_comparisons",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_policy_comparisons_comparison_id",
        "c4_policy_comparisons",
        ["comparison_id"],
        unique=True,
    )

    # 3. Create c4_regression_plans table
    op.create_table(
        "c4_regression_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("comparison_id", sa.String(length=128), nullable=False),
        sa.Column("baseline_contract_id", sa.String(length=128), nullable=False),
        sa.Column("baseline_contract_version", sa.Integer(), nullable=False),
        sa.Column("candidate_contract_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_contract_version", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id"),
    )
    op.create_index(
        "ix_c4_regression_plans_project_id",
        "c4_regression_plans",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_regression_plans_plan_id",
        "c4_regression_plans",
        ["plan_id"],
        unique=True,
    )
    op.create_index(
        "ix_c4_regression_plans_comparison_id",
        "c4_regression_plans",
        ["comparison_id"],
        unique=False,
    )

    # 4. Create c4_regression_batches table
    op.create_table(
        "c4_regression_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_contract_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_contract_version", sa.Integer(), nullable=False),
        sa.Column("adapter_id", sa.String(length=128), nullable=False),
        sa.Column("execution_mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_digest", sa.String(length=64), nullable=True),
        sa.Column("batch_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id"),
        sa.UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_c4_regression_batches_proj_idempotency",
        ),
    )
    op.create_index(
        "ix_c4_regression_batches_project_id",
        "c4_regression_batches",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_regression_batches_plan_id",
        "c4_regression_batches",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_regression_batches_batch_id",
        "c4_regression_batches",
        ["batch_id"],
        unique=True,
    )
    op.create_index(
        "ix_c4_regression_batches_idempotency_key",
        "c4_regression_batches",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("c4_regression_batches")
    op.drop_table("c4_regression_plans")
    op.drop_table("c4_policy_comparisons")
    op.drop_constraint(
        "uq_c4_execution_runs_proj_idempotency",
        "c4_execution_runs",
        type_="unique",
    )
