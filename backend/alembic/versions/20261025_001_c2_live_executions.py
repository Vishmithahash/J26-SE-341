"""Create the C2 live execution tracking table.

Revision ID: 20261025_001_c2_live_executions
Revises: 20261024_002_repair_schemas
Create Date: 2026-10-25 18:00:00.000000

Component: C2 State-Aware Multi-Step Workflow Testing (live NexaCart execution).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision: str = "20261025_001_c2_live_executions"
down_revision: str | Sequence[str] | None = "20261024_002_repair_schemas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    if (
        not context.is_offline_mode()
        and "c2_live_executions" in sa.inspect(op.get_bind()).get_table_names()
    ):
        return
    op.create_table(
        "c2_live_executions",
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("planned_test_ids", json_type, nullable=False),
        sa.Column("case_results", json_type, nullable=False),
        sa.Column("summary", json_type, nullable=False),
        sa.Column("configuration_snapshot", json_type, nullable=False),
        sa.Column("halt_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index(
        "ix_c2_live_executions_project_id", "c2_live_executions", ["project_id"]
    )
    op.create_index(
        "ix_c2_live_executions_suite_id", "c2_live_executions", ["suite_id"]
    )
    op.create_index("ix_c2_live_executions_status", "c2_live_executions", ["status"])
    op.create_index(
        "ix_c2_live_execution_lookup",
        "c2_live_executions",
        ["project_id", "suite_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_c2_live_execution_lookup", table_name="c2_live_executions")
    op.drop_index("ix_c2_live_executions_status", table_name="c2_live_executions")
    op.drop_index("ix_c2_live_executions_suite_id", table_name="c2_live_executions")
    op.drop_index("ix_c2_live_executions_project_id", table_name="c2_live_executions")
    op.drop_table("c2_live_executions")
