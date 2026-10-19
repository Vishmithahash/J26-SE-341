"""Create C4 Phase 4 onboarding tables and execution outcome columns

Revision ID: 20261020_004_c4
Revises: 20261020_003_c4
Create Date: 2026-10-20 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_004_c4"
down_revision: str | Sequence[str] | None = "20261020_003_c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add Phase 4 outcome separation columns to c4_execution_runs
    op.add_column(
        "c4_execution_runs",
        sa.Column("request_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "c4_execution_runs",
        sa.Column("injection_target_verdict", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "c4_execution_runs",
        sa.Column("attempt_goal_outcome", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "c4_execution_runs",
        sa.Column("commit_goal_outcome", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "c4_execution_runs",
        sa.Column(
            "backend_rejection_observed",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )

    # 2. Create c4_extraction_jobs table
    op.create_table(
        "c4_extraction_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_identifier", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("readiness_status", sa.String(length=32), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("job_metadata", sa.JSON(), nullable=False),
        sa.Column("candidates_extracted", sa.JSON(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_c4_extraction_jobs_job_id"),
    )
    op.create_index(
        op.f("ix_c4_extraction_jobs_project_id"),
        "c4_extraction_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_extraction_jobs_job_id"),
        "c4_extraction_jobs",
        ["job_id"],
        unique=False,
    )

    # 3. Create c4_onboarding_jobs table
    op.create_table(
        "c4_onboarding_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("domain_id", sa.String(length=128), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("extraction_job_id", sa.String(length=128), nullable=True),
        sa.Column("draft_contract_id", sa.String(length=128), nullable=True),
        sa.Column("contract_version", sa.Integer(), nullable=True),
        sa.Column("batch_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=False),
        sa.Column("step_results", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_c4_onboarding_jobs_job_id"),
    )
    op.create_index(
        op.f("ix_c4_onboarding_jobs_project_id"),
        "c4_onboarding_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_onboarding_jobs_job_id"),
        "c4_onboarding_jobs",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_c4_onboarding_jobs_job_id"), table_name="c4_onboarding_jobs")
    op.drop_index(op.f("ix_c4_onboarding_jobs_project_id"), table_name="c4_onboarding_jobs")
    op.drop_table("c4_onboarding_jobs")

    op.drop_index(op.f("ix_c4_extraction_jobs_job_id"), table_name="c4_extraction_jobs")
    op.drop_index(op.f("ix_c4_extraction_jobs_project_id"), table_name="c4_extraction_jobs")
    op.drop_table("c4_extraction_jobs")

    op.drop_column("c4_execution_runs", "backend_rejection_observed")
    op.drop_column("c4_execution_runs", "commit_goal_outcome")
    op.drop_column("c4_execution_runs", "attempt_goal_outcome")
    op.drop_column("c4_execution_runs", "injection_target_verdict")
    op.drop_column("c4_execution_runs", "request_digest")
