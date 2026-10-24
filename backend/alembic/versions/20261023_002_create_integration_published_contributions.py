"""Create integration published contributions table.

Revision ID: 20261023_published_contributions
Revises: 20261023_integration_reports
Create Date: 2026-10-23 00:00:00.000000

Component: Shared Integration Reporting & Replay (Part 3)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261023_published_contributions"
down_revision: str | Sequence[str] | None = "20261023_integration_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Create integration published contributions table."""
    op.create_table(
        "integration_published_contributions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("component_type", sa.String(length=16), nullable=False),
        sa.Column("contribution_id", sa.String(length=128), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=True),
        sa.Column("publication_token", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_token"),
        sa.UniqueConstraint("project_id", "contribution_id", name="uq_project_contribution_id"),
    )
    op.create_index(
        "ix_published_contribution_lookup",
        "integration_published_contributions",
        ["project_id", "component_type", "contribution_id"],
    )


def downgrade() -> None:
    """Drop integration published contributions table."""
    op.drop_index("ix_published_contribution_lookup", table_name="integration_published_contributions")
    op.drop_table("integration_published_contributions")
