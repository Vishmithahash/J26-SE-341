"""Create shared projects, input references, and event history tables.

Revision ID: 20261021_projects
Revises: f9e187209bbb
Create Date: 2026-10-21 00:00:00.000000

Component: Shared Projects Workspace
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261021_projects"
down_revision: str | Sequence[str] | None = "f9e187209bbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shared projects, input references, and project history events tables."""
    op.create_table(
        "projects",
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=64), server_default="custom", nullable=False),
        sa.Column("environment", sa.String(length=32), server_default="development", nullable=False),
        sa.Column("backend_base_url", sa.String(length=1024), nullable=False),
        sa.Column("backend_health_url", sa.String(length=1024), nullable=False),
        sa.Column("agent_endpoint", sa.String(length=1024), nullable=True),
        sa.Column("agent_health_url", sa.String(length=1024), nullable=True),
        sa.Column("repository_url", sa.String(length=1024), nullable=True),
        sa.Column("configuration_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("lifecycle", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("connection_state", sa.String(length=32), server_default="NOT_CHECKED", nullable=False),
        sa.Column("last_check_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.create_index(op.f("ix_projects_project_id"), "projects", ["project_id"], unique=False)
    op.create_index(op.f("ix_projects_owner_user_id"), "projects", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_projects_lifecycle"), "projects", ["lifecycle"], unique=False)
    op.create_index(op.f("ix_projects_connection_state"), "projects", ["connection_state"], unique=False)

    op.create_table(
        "project_input_references",
        sa.Column("reference_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("reference_location", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=64), server_default="1.0.0", nullable=False),
        sa.Column("registered_at_utc", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("reference_id"),
    )
    op.create_index(op.f("ix_project_input_references_reference_id"), "project_input_references", ["reference_id"], unique=False)
    op.create_index(op.f("ix_project_input_references_project_id"), "project_input_references", ["project_id"], unique=False)

    op.create_table(
        "project_history_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("acting_account_id", sa.Integer(), nullable=False),
        sa.Column("acting_account_email", sa.String(length=255), nullable=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("resulting_state", sa.JSON(), nullable=True),
        sa.Column("safe_details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_project_history_events_event_id"), "project_history_events", ["event_id"], unique=False)
    op.create_index(op.f("ix_project_history_events_project_id"), "project_history_events", ["project_id"], unique=False)


def downgrade() -> None:
    """Drop shared projects, input references, and project history events tables."""
    op.drop_index(op.f("ix_project_history_events_project_id"), table_name="project_history_events")
    op.drop_index(op.f("ix_project_history_events_event_id"), table_name="project_history_events")
    op.drop_table("project_history_events")

    op.drop_index(op.f("ix_project_input_references_project_id"), table_name="project_input_references")
    op.drop_index(op.f("ix_project_input_references_reference_id"), table_name="project_input_references")
    op.drop_table("project_input_references")

    op.drop_index(op.f("ix_projects_connection_state"), table_name="projects")
    op.drop_index(op.f("ix_projects_lifecycle"), table_name="projects")
    op.drop_index(op.f("ix_projects_owner_user_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_project_id"), table_name="projects")
    op.drop_table("projects")
