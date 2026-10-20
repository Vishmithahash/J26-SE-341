"""Create C1 corrections table

Revision ID: c1_0005
Revises: c1_0004
Create Date: 2026-10-20 10:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0005"
down_revision: str | None = "c1_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(
        op.f("ix_c1_corrections_idempotency_key"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_status"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_diagnosis_id"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_case_id"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_case_execution_id"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_run_id"),
        table_name="c1_corrections",
    )
    op.drop_index(
        op.f("ix_c1_corrections_project_id"),
        table_name="c1_corrections",
    )
    op.drop_table("c1_corrections")
