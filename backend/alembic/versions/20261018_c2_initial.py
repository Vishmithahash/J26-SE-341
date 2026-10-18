"""C2 initial migration: create c2_workflow_models and c2_validation_reports tables.

Revision ID: c2_001_initial
Revises: None
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2_001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. Create c2_workflow_models table
    op.create_table(
        "c2_workflow_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            server_default="2026.1",
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", json_type, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "lifecycle_status",
            sa.String(length=24),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("review_basis", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "model_id", "version", name="uq_c2_model_project_id_version"
        ),
    )
    op.create_index(
        "ix_c2_workflow_models_project_id", "c2_workflow_models", ["project_id"]
    )
    op.create_index(
        "ix_c2_workflow_models_model_id", "c2_workflow_models", ["model_id"]
    )
    op.create_index("ix_c2_workflow_models_version", "c2_workflow_models", ["version"])
    op.create_index(
        "ix_c2_workflow_models_content_hash", "c2_workflow_models", ["content_hash"]
    )
    op.create_index(
        "ix_c2_workflow_models_lifecycle_status",
        "c2_workflow_models",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_c2_model_lookup",
        "c2_workflow_models",
        ["project_id", "model_id", "version"],
    )

    # 2. Create c2_validation_reports table
    op.create_table(
        "c2_validation_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_record_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("readiness", sa.String(length=24), nullable=False),
        sa.Column("summary", json_type, nullable=False),
        sa.Column("errors", json_type, nullable=False),
        sa.Column("warnings", json_type, nullable=False),
        sa.Column("diagnostics", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["model_record_id"], ["c2_workflow_models.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_c2_validation_reports_model_record_id",
        "c2_validation_reports",
        ["model_record_id"],
    )
    op.create_index(
        "ix_c2_validation_reports_project_id", "c2_validation_reports", ["project_id"]
    )
    op.create_index(
        "ix_c2_validation_reports_model_id", "c2_validation_reports", ["model_id"]
    )
    op.create_index(
        "ix_c2_validation_reports_version", "c2_validation_reports", ["version"]
    )
    op.create_index(
        "ix_c2_validation_reports_content_hash",
        "c2_validation_reports",
        ["content_hash"],
    )
    op.create_index(
        "ix_c2_report_lookup",
        "c2_validation_reports",
        ["project_id", "model_id", "version", "content_hash"],
    )


def downgrade() -> None:
    op.drop_table("c2_validation_reports")
    op.drop_table("c2_workflow_models")
