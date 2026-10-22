"""Create shared integration run plans, identifier mappings, and artifact references tables.

Revision ID: 20261022_integration
Revises: 20261021_projects
Create Date: 2026-10-22 00:00:00.000000

Component: Shared Integration Foundation (Part 1)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261022_integration"
down_revision: str | Sequence[str] | None = "20261021_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Create integration run plans, identifier mappings, and artifact references tables."""
    op.create_table(
        "integration_run_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
            server_default="2026.1",
        ),
        sa.Column(
            "lifecycle_status",
            sa.String(length=32),
            nullable=False,
            server_default="PLANNED",
        ),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_payload", JSON_TYPE, nullable=False),
        sa.Column("readiness_report", JSON_TYPE, nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_run_id", name="uq_integration_run_plans_run_id"
        ),
    )
    op.create_index(
        "ix_integration_run_plans_run_id",
        "integration_run_plans",
        ["integration_run_id"],
    )
    op.create_index(
        "ix_integration_run_plans_project_id",
        "integration_run_plans",
        ["project_id"],
    )
    op.create_index(
        "ix_integration_run_plans_status",
        "integration_run_plans",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_integration_run_plans_digest",
        "integration_run_plans",
        ["plan_digest"],
    )

    op.create_table(
        "integration_identifier_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("integration_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("component_type", sa.String(length=16), nullable=False),
        sa.Column("native_entity_type", sa.String(length=64), nullable=False),
        sa.Column("native_id", sa.String(length=128), nullable=False),
        sa.Column("step_or_trial_index", sa.Integer(), nullable=True),
        sa.Column("context_json", JSON_TYPE, nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["integration_run_id"],
            ["integration_run_plans.integration_run_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_run_id",
            "component_type",
            "native_entity_type",
            "native_id",
            name="uq_integration_id_mapping",
        ),
    )
    op.create_index(
        "ix_integration_identifier_mappings_run_id",
        "integration_identifier_mappings",
        ["integration_run_id"],
    )
    op.create_index(
        "ix_integration_identifier_mappings_project_id",
        "integration_identifier_mappings",
        ["project_id"],
    )
    op.create_index(
        "ix_integration_identifier_mappings_component",
        "integration_identifier_mappings",
        ["component_type"],
    )
    op.create_index(
        "ix_integration_identifier_mappings_native_id",
        "integration_identifier_mappings",
        ["native_id"],
    )

    op.create_table(
        "integration_artifact_references",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("integration_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("component_type", sa.String(length=16), nullable=False),
        sa.Column("artifact_category", sa.String(length=64), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["integration_run_id"],
            ["integration_run_plans.integration_run_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_artifact_references_run_id",
        "integration_artifact_references",
        ["integration_run_id"],
    )
    op.create_index(
        "ix_integration_artifact_references_project_id",
        "integration_artifact_references",
        ["project_id"],
    )
    op.create_index(
        "ix_integration_artifact_references_component",
        "integration_artifact_references",
        ["component_type"],
    )


def downgrade() -> None:
    """Drop integration tables in reverse dependency order."""
    op.drop_table("integration_artifact_references")
    op.drop_table("integration_identifier_mappings")
    op.drop_table("integration_run_plans")
