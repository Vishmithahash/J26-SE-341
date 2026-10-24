"""Create user model selections table.

Revision ID: 20261024_user_model_selections
Revises: 20261023_published_contributions
Create Date: 2026-10-24 00:00:00.000000

Component: Shared LLM Integration Layer
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261024_user_model_selections"
down_revision: str | Sequence[str] | None = "20261023_published_contributions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Create user_model_selections table."""
    op.create_table(
        "user_model_selections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("connection_type", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="ollama"),
        sa.Column("model_id", sa.String(length=128), nullable=False, server_default="qwen3:4b"),
        sa.Column("generation_settings", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_test_status", sa.String(length=32), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_model_selections_user_id"),
    )
    op.create_index(
        "ix_user_model_selections_user_id",
        "user_model_selections",
        ["user_id"],
    )


def downgrade() -> None:
    """Drop user_model_selections table."""
    op.drop_index("ix_user_model_selections_user_id", table_name="user_model_selections")
    op.drop_table("user_model_selections")
