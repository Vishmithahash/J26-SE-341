"""C2 test generation migration: create c2_test_suites and c2_test_cases tables.

Revision ID: c2_002_generation
Revises: c2_001_initial
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2_002_generation"
down_revision: str | Sequence[str] | None = "c2_001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. Create c2_test_suites table
    op.create_table(
        "c2_test_suites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=64), nullable=False),
        sa.Column("model_record_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("model_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "generator_version",
            sa.String(length=32),
            server_default="c2_generator_v1",
            nullable=False,
        ),
        sa.Column("seed", sa.Integer(), server_default=sa.text("42"), nullable=False),
        sa.Column("config", json_type, nullable=False),
        sa.Column("diagnostics", json_type, nullable=False),
        sa.Column(
            "total_cases",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "ready_cases_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "not_ready_cases_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("category_counts", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["model_record_id"], ["c2_workflow_models.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "project_id", "suite_id", name="uq_c2_suite_project_id_suite_id"
        ),
    )
    op.create_index("ix_c2_test_suites_project_id", "c2_test_suites", ["project_id"])
    op.create_index("ix_c2_test_suites_suite_id", "c2_test_suites", ["suite_id"])
    op.create_index(
        "ix_c2_test_suites_model_record_id", "c2_test_suites", ["model_record_id"]
    )
    op.create_index("ix_c2_test_suites_model_id", "c2_test_suites", ["model_id"])
    op.create_index(
        "ix_c2_test_suites_model_version", "c2_test_suites", ["model_version"]
    )
    op.create_index(
        "ix_c2_test_suites_model_content_hash",
        "c2_test_suites",
        ["model_content_hash"],
    )
    op.create_index("ix_c2_suite_lookup", "c2_test_suites", ["project_id", "suite_id"])

    # 2. Create c2_test_cases table
    op.create_table(
        "c2_test_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("suite_record_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=64), nullable=False),
        sa.Column("test_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "execution_mode",
            sa.String(length=32),
            server_default="live_agent",
            nullable=False,
        ),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("fixture_ref", sa.String(length=128), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("definition", json_type, nullable=False),
        sa.Column(
            "readiness",
            sa.String(length=32),
            server_default="TEST_READY",
            nullable=False,
        ),
        sa.Column("readiness_reasons", json_type, nullable=False),
        sa.Column(
            "is_ready",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["suite_record_id"], ["c2_test_suites.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "project_id",
            "suite_id",
            "test_id",
            name="uq_c2_test_case_project_suite_test",
        ),
    )
    op.create_index(
        "ix_c2_test_cases_suite_record_id", "c2_test_cases", ["suite_record_id"]
    )
    op.create_index("ix_c2_test_cases_project_id", "c2_test_cases", ["project_id"])
    op.create_index("ix_c2_test_cases_suite_id", "c2_test_cases", ["suite_id"])
    op.create_index("ix_c2_test_cases_test_id", "c2_test_cases", ["test_id"])
    op.create_index("ix_c2_test_cases_category", "c2_test_cases", ["category"])
    op.create_index("ix_c2_test_cases_readiness", "c2_test_cases", ["readiness"])
    op.create_index("ix_c2_test_cases_is_ready", "c2_test_cases", ["is_ready"])
    op.create_index(
        "ix_c2_test_case_lookup",
        "c2_test_cases",
        ["project_id", "suite_id", "test_id"],
    )


def downgrade() -> None:
    op.drop_table("c2_test_cases")
    op.drop_table("c2_test_suites")
