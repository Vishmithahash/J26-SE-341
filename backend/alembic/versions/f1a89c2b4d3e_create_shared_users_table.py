"""create_shared_users_table

Revision ID: f1a89c2b4d3e
Revises: e75342624f8c
Create Date: 2026-10-20 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a89c2b4d3e"
down_revision: str | Sequence[str] | None = "e75342624f8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema by creating shared users table."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("canonical_email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "USER", name="user_role", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_users_canonical_email"),
        "users",
        ["canonical_email"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema by dropping shared users table."""
    op.drop_index(op.f("ix_users_canonical_email"), table_name="users")
    op.drop_table("users")
