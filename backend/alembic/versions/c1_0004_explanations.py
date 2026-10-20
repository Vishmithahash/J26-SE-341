"""Create C1 case diagnoses and explanations table

Revision ID: c1_0004
Revises: c1_0003
Create Date: 2026-10-20 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0004"
down_revision: str | None = "c1_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(
        op.f("ix_c1_case_diagnoses_idempotency_key"),
        table_name="c1_case_diagnoses",
    )
    op.drop_index(
        op.f("ix_c1_case_diagnoses_cause_category"),
        table_name="c1_case_diagnoses",
    )
    op.drop_index(
        op.f("ix_c1_case_diagnoses_case_id"),
        table_name="c1_case_diagnoses",
    )
    op.drop_index(
        op.f("ix_c1_case_diagnoses_case_execution_id"),
        table_name="c1_case_diagnoses",
    )
    op.drop_index(
        op.f("ix_c1_case_diagnoses_run_id"),
        table_name="c1_case_diagnoses",
    )
    op.drop_index(
        op.f("ix_c1_case_diagnoses_project_id"),
        table_name="c1_case_diagnoses",
    )
    op.drop_table("c1_case_diagnoses")
