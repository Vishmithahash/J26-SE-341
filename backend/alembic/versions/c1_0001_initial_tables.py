"""Create C1 Component 1 project configurations and suite versions tables

Revision ID: c1_0001
Revises: None
Create Date: 2026-10-19 13:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "c1_project_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "is_immutable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("agent_connection_ref", sa.String(length=255), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("tool_constraints", sa.JSON(), nullable=False),
        sa.Column("expectations", sa.JSON(), nullable=False),
        sa.Column("synthetic_fixture_refs", sa.JSON(), nullable=False),
        sa.Column("reset_capability", sa.JSON(), nullable=True),
        sa.Column("trace_capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "version", name="uq_c1_project_config_version"
        ),
    )
    op.create_index(
        op.f("ix_c1_project_configs_project_id"),
        "c1_project_configs",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "c1_suite_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=100), nullable=False),
        sa.Column("suite_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("config_id", sa.String(length=36), nullable=False),
        sa.Column(
            "is_immutable", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["config_id"], ["c1_project_configs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "suite_id", "version", name="uq_c1_suite_version"
        ),
    )
    op.create_index(
        op.f("ix_c1_suite_versions_project_id"),
        "c1_suite_versions",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_c1_suite_versions_project_id"), table_name="c1_suite_versions"
    )
    op.drop_table("c1_suite_versions")
    op.drop_index(
        op.f("ix_c1_project_configs_project_id"), table_name="c1_project_configs"
    )
    op.drop_table("c1_project_configs")
