"""Create shared integration reports table.

Revision ID: 20261023_integration_reports
Revises: 20261023_integration_executions
Create Date: 2026-10-23 00:00:00.000000

Component: Shared Integration Reporting & Replay (Part 3)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261023_integration_reports"
down_revision: str | Sequence[str] | None = "20261023_integration_executions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Create integration reports table."""
    op.create_table(
        "integration_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("integration_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "report_status",
            sa.String(length=32),
            nullable=False,
            server_default="PUBLISHED",
        ),
        sa.Column("report_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "raw_finding_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "grouped_defect_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("report_payload", JSON_TYPE, nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["integration_executions.execution_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_run_id"],
            ["integration_run_plans.integration_run_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_reports_report_id",
        "integration_reports",
        ["report_id"],
        unique=True,
    )
    op.create_index(
        "ix_integration_reports_execution_id",
        "integration_reports",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        "ix_integration_reports_integration_run_id",
        "integration_reports",
        ["integration_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_integration_reports_project_id",
        "integration_reports",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_integration_reports_report_status",
        "integration_reports",
        ["report_status"],
        unique=False,
    )
    op.create_index(
        "ix_integration_reports_published_by_user_id",
        "integration_reports",
        ["published_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop integration reports table."""
    op.drop_index(
        "ix_integration_reports_published_by_user_id", table_name="integration_reports"
    )
    op.drop_index(
        "ix_integration_reports_report_status", table_name="integration_reports"
    )
    op.drop_index("ix_integration_reports_project_id", table_name="integration_reports")
    op.drop_index(
        "ix_integration_reports_integration_run_id", table_name="integration_reports"
    )
    op.drop_index(
        "ix_integration_reports_execution_id", table_name="integration_reports"
    )
    op.drop_index("ix_integration_reports_report_id", table_name="integration_reports")
    op.drop_table("integration_reports")
