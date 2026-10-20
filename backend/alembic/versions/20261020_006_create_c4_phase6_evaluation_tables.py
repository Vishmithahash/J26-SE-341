"""Create C4 Phase 6 evaluation tables for datasets, reviews, experiments, and historical re-evaluations

Revision ID: 20261020_006_c4
Revises: 20261020_005_c4
Create Date: 2026-10-20 05:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_006_c4"
down_revision: str | Sequence[str] | None = "20261020_005_c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create c4_historical_re_evaluations table
    op.create_table(
        "c4_historical_re_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("re_eval_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_id", sa.String(length=128), nullable=False),
        sa.Column("original_contract_id", sa.String(length=128), nullable=False),
        sa.Column("original_contract_version", sa.Integer(), nullable=False),
        sa.Column("candidate_contract_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_contract_version", sa.Integer(), nullable=False),
        sa.Column("derived_policy_verdict", sa.String(length=32), nullable=False),
        sa.Column("re_eval_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("re_eval_id"),
    )
    op.create_index(
        "ix_c4_historical_re_evaluations_project_id",
        "c4_historical_re_evaluations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_historical_re_evaluations_re_eval_id",
        "c4_historical_re_evaluations",
        ["re_eval_id"],
        unique=True,
    )
    op.create_index(
        "ix_c4_historical_re_evaluations_source_run_id",
        "c4_historical_re_evaluations",
        ["source_run_id"],
        unique=False,
    )

    # 2. Create c4_evaluation_datasets table
    op.create_table(
        "c4_evaluation_datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("domain_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dataset_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "dataset_id",
            "version",
            name="uq_c4_eval_datasets_proj_id_ver",
        ),
    )
    op.create_index(
        "ix_c4_evaluation_datasets_project_id",
        "c4_evaluation_datasets",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_evaluation_datasets_dataset_id",
        "c4_evaluation_datasets",
        ["dataset_id"],
        unique=False,
    )

    # 3. Create c4_evaluation_reviews table
    op.create_table(
        "c4_evaluation_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("verdict_decision", sa.String(length=32), nullable=False),
        sa.Column("review_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )
    op.create_index(
        "ix_c4_evaluation_reviews_project_id",
        "c4_evaluation_reviews",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_evaluation_reviews_review_id",
        "c4_evaluation_reviews",
        ["review_id"],
        unique=True,
    )
    op.create_index(
        "ix_c4_evaluation_reviews_case_id",
        "c4_evaluation_reviews",
        ["case_id"],
        unique=False,
    )

    # 4. Create c4_experiments table
    op.create_table(
        "c4_experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("domain_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=False),
        sa.Column("strategy_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("experiment_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id"),
    )
    op.create_index(
        "ix_c4_experiments_project_id",
        "c4_experiments",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c4_experiments_experiment_id",
        "c4_experiments",
        ["experiment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("c4_experiments")
    op.drop_table("c4_evaluation_reviews")
    op.drop_table("c4_evaluation_datasets")
    op.drop_table("c4_historical_re_evaluations")
