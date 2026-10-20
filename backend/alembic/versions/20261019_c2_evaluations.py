"""C2 evaluation results migration: create c2_evaluation_results table.

Revision ID: c2_003_evaluations
Revises: c2_002_generation
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2_003_evaluations"
down_revision: str | Sequence[str] | None = "c2_002_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "c2_evaluation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=64), nullable=False),
        sa.Column("test_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("model_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "evaluator_version",
            sa.String(length=32),
            server_default="c2_evaluator_v1",
            nullable=False,
        ),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("reasons", json_type, nullable=False),
        sa.Column("violations", json_type, nullable=False),
        sa.Column("first_divergence", json_type, nullable=True),
        sa.Column("coverage", json_type, nullable=False),
        sa.Column("expected_states", json_type, nullable=False),
        sa.Column("observed_states", json_type, nullable=False),
        sa.Column("evidence_references", json_type, nullable=False),
        sa.Column(
            "evaluator_timing_ms",
            sa.Float(),
            server_default=sa.text("0.0"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "suite_id",
            "test_id",
            "run_id",
            name="uq_c2_evaluation_run",
        ),
    )

    op.create_index(
        "ix_c2_evaluation_results_project_id",
        "c2_evaluation_results",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_suite_id",
        "c2_evaluation_results",
        ["suite_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_test_id",
        "c2_evaluation_results",
        ["test_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_run_id",
        "c2_evaluation_results",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_model_id",
        "c2_evaluation_results",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_verdict",
        "c2_evaluation_results",
        ["verdict"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_lookup",
        "c2_evaluation_results",
        ["project_id", "suite_id", "test_id"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_verdict",
        "c2_evaluation_results",
        ["project_id", "verdict"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_c2_evaluation_verdict", table_name="c2_evaluation_results")
    op.drop_index("ix_c2_evaluation_lookup", table_name="c2_evaluation_results")
    op.drop_index(
        "ix_c2_evaluation_results_verdict", table_name="c2_evaluation_results"
    )
    op.drop_index(
        "ix_c2_evaluation_results_model_id", table_name="c2_evaluation_results"
    )
    op.drop_index("ix_c2_evaluation_results_run_id", table_name="c2_evaluation_results")
    op.drop_index(
        "ix_c2_evaluation_results_test_id", table_name="c2_evaluation_results"
    )
    op.drop_index(
        "ix_c2_evaluation_results_suite_id", table_name="c2_evaluation_results"
    )
    op.drop_index(
        "ix_c2_evaluation_results_project_id", table_name="c2_evaluation_results"
    )
    op.drop_table("c2_evaluation_results")
