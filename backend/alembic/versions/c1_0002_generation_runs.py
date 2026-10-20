"""Create C1 generation runs table and add content hash to suite versions

Revision ID: c1_0002
Revises: c1_0001
Create Date: 2026-10-19 14:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0002"
down_revision: str | None = "c1_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "c1_generation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=100), nullable=False),
        sa.Column("config_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=100), nullable=True),
        sa.Column("suite_version_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["config_id"], ["c1_project_configs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_c1_generation_runs_project_id"),
        "c1_generation_runs",
        ["project_id"],
        unique=False,
    )

    op.add_column(
        "c1_suite_versions",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "c1_suite_versions",
        sa.Column("generation_run_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("c1_suite_versions", "generation_run_id")
    op.drop_column("c1_suite_versions", "content_hash")
    op.drop_index(
        op.f("ix_c1_generation_runs_project_id"), table_name="c1_generation_runs"
    )
    op.drop_table("c1_generation_runs")
