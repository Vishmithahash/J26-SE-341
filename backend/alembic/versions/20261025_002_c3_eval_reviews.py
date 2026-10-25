"""Create the C3 evaluation review table.

Revision ID: 20261025_002_c3_eval_reviews
Revises: 20261025_001_c2_live_executions
Create Date: 2026-10-25 20:00:00.000000

Component: C3 Robustness and Failure Recovery Testing (append-only reviewer labels).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20261025_002_c3_eval_reviews"
down_revision: str | Sequence[str] | None = "20261025_001_c2_live_executions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if (
        not context.is_offline_mode()
        and "c3_evaluation_reviews" in sa.inspect(op.get_bind()).get_table_names()
    ):
        return
    op.create_table(
        "c3_evaluation_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("evaluation_id", sa.String(length=128), nullable=False),
        sa.Column("pair_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("evaluator_verdict", sa.String(length=32), nullable=True),
        sa.Column("reviewer_verdict", sa.String(length=32), nullable=False),
        sa.Column("evidence_sufficient", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_email", sa.String(length=255), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["c3_evaluations.evaluation_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_c3_evaluation_reviews_review_id",
        "c3_evaluation_reviews",
        ["review_id"],
        unique=True,
    )
    for column in ("evaluation_id", "pair_id", "project_id"):
        op.create_index(
            f"ix_c3_evaluation_reviews_{column}", "c3_evaluation_reviews", [column]
        )


def downgrade() -> None:
    op.drop_table("c3_evaluation_reviews")
