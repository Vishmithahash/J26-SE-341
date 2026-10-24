"""Create shared integration executions table.

Revision ID: 20261023_integration_executions
Revises: 20261022_integration
Create Date: 2026-10-23 00:00:00.000000

Component: Shared Integration Coordination (Part 2)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261023_integration_executions"
down_revision: str | Sequence[str] | None = "20261022_integration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Create integration executions table."""
    op.create_table(
        "integration_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("integration_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "target_mode",
            sa.String(length=32),
            nullable=False,
            server_default="CONTROLLED_TEST",
        ),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("retained_evidence_digest", sa.String(length=64), nullable=True),
        sa.Column("retained_evidence", JSON_TYPE, nullable=True),
        sa.Column("evaluations", JSON_TYPE, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["integration_run_id"],
            ["integration_run_plans.integration_run_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_executions_execution_id",
        "integration_executions",
        ["execution_id"],
        unique=True,
    )
    op.create_index(
        "ix_integration_executions_integration_run_id",
        "integration_executions",
        ["integration_run_id"],
    )
    op.create_index(
        "ix_integration_executions_project_id",
        "integration_executions",
        ["project_id"],
    )
    op.create_index(
        "ix_integration_executions_lifecycle_status",
        "integration_executions",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_integration_executions_triggered_by_user_id",
        "integration_executions",
        ["triggered_by_user_id"],
    )


def downgrade() -> None:
    """Drop integration executions table."""
    op.drop_index(
        "ix_integration_executions_triggered_by_user_id",
        table_name="integration_executions",
    )
    op.drop_index(
        "ix_integration_executions_lifecycle_status",
        table_name="integration_executions",
    )
    op.drop_index(
        "ix_integration_executions_project_id",
        table_name="integration_executions",
    )
    op.drop_index(
        "ix_integration_executions_integration_run_id",
        table_name="integration_executions",
    )
    op.drop_index(
        "ix_integration_executions_execution_id",
        table_name="integration_executions",
    )
    op.drop_table("integration_executions")
