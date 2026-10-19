"""C2 experiments, baseline comparisons, and ground-truth dataset manifests.

Revision ID: c2_005_experiments_and_baselines
Revises: c2_004_integration_coverage
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2_005_experiments_and_baselines"
down_revision: str | Sequence[str] | None = "c2_004_integration_coverage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. Create table c2_experiment_datasets
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
        sa.Column("development_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("held_out_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("manifest_payload", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "dataset_id", "version", name="uq_c2_dataset_project_id_version"
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

    # 2. Create table c2_experiments
    op.create_table(
        "c2_experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("experiment_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("dataset_record_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
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

    # 3. Create table c2_experiment_case_results
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
        sa.Column("can_localize", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("first_divergence_predicted_step", sa.Integer(), nullable=True),
        sa.Column("first_divergence_event_id", sa.String(length=64), nullable=True),
        sa.Column("evaluator_timing_ms", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("evidence_digest_consumed", sa.String(length=64), nullable=False),
        sa.Column("is_excluded", sa.Boolean(), server_default="false", nullable=False),
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
    op.create_index(
        "ix_c2_experiment_case_results_verdict",
        "c2_experiment_case_results",
        ["verdict"],
        unique=False,
    )
    op.create_index(
        "ix_c2_exp_case_lookup",
        "c2_experiment_case_results",
        ["project_id", "experiment_id", "case_id", "method_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("c2_experiment_case_results")
    op.drop_table("c2_experiments")
    op.drop_table("c2_experiment_datasets")
