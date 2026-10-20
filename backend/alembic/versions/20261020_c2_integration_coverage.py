"""C2 integration evidence, additive evaluation attempts, and coverage migration.

Revision ID: c2_004_integration_coverage
Revises: c2_003_evaluations
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2_004_integration_coverage"
down_revision: str | Sequence[str] | None = "c2_003_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. Create table c2_execution_evidence
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

    # 2. Add columns to c2_evaluation_results
    with op.batch_alter_table("c2_evaluation_results", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "execution_evidence_id",
                sa.String(length=36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "evaluator_config",
                json_type,
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "evaluation_attempt",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "evidence_digest",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "reproduced_from_evaluation_id",
                sa.String(length=36),
                nullable=True,
            )
        )
        # Drop old single-run constraint and replace with attempt-aware constraint
        batch_op.drop_constraint("uq_c2_evaluation_run", type_="unique")
        batch_op.create_unique_constraint(
            "uq_c2_evaluation_attempt",
            [
                "project_id",
                "suite_id",
                "test_id",
                "run_id",
                "evaluator_version",
                "evaluation_attempt",
            ],
        )

    op.create_index(
        "ix_c2_evaluation_results_evidence_digest",
        "c2_evaluation_results",
        ["evidence_digest"],
        unique=False,
    )
    op.create_index(
        "ix_c2_evaluation_results_exec_evidence_id",
        "c2_evaluation_results",
        ["execution_evidence_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_c2_evaluation_results_exec_evidence_id",
        table_name="c2_evaluation_results",
    )
    op.drop_index(
        "ix_c2_evaluation_results_evidence_digest",
        table_name="c2_evaluation_results",
    )

    with op.batch_alter_table("c2_evaluation_results", schema=None) as batch_op:
        batch_op.drop_constraint("uq_c2_evaluation_attempt", type_="unique")
        batch_op.create_unique_constraint(
            "uq_c2_evaluation_run",
            ["project_id", "suite_id", "test_id", "run_id"],
        )
        batch_op.drop_column("reproduced_from_evaluation_id")
        batch_op.drop_column("evidence_digest")
        batch_op.drop_column("evaluation_attempt")
        batch_op.drop_column("evaluator_config")
        batch_op.drop_column("execution_evidence_id")

    op.drop_index("ix_c2_execution_lookup", table_name="c2_execution_evidence")
    op.drop_index("ix_c2_execution_evidence_digest", table_name="c2_execution_evidence")
    op.drop_index("ix_c2_execution_evidence_run_id", table_name="c2_execution_evidence")
    op.drop_index(
        "ix_c2_execution_evidence_test_id", table_name="c2_execution_evidence"
    )
    op.drop_index(
        "ix_c2_execution_evidence_suite_id", table_name="c2_execution_evidence"
    )
    op.drop_index(
        "ix_c2_execution_evidence_project_id", table_name="c2_execution_evidence"
    )
    op.drop_table("c2_execution_evidence")
