"""Create C1 reference labels table for research evaluation

Revision ID: c1_0006
Revises: c1_0005
Create Date: 2026-10-20 11:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1_0006"
down_revision: str | None = "c1_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "c1_reference_labels",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=100), nullable=False),
        sa.Column("case_id", sa.String(length=100), nullable=False),
        sa.Column("suite_id", sa.String(length=100), nullable=True),
        sa.Column("task_family", sa.String(length=100), nullable=False),
        sa.Column("dataset_split", sa.String(length=50), nullable=False),
        sa.Column("ground_truth_verdict", sa.String(length=50), nullable=False),
        sa.Column("ground_truth_cause", sa.String(length=50), nullable=True),
        sa.Column("ground_truth_code_locations", sa.JSON(), nullable=False),
        sa.Column("valid_evidence_refs", sa.JSON(), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), nullable=False),
        sa.Column("label_version", sa.String(length=50), nullable=False),
        sa.Column("disagreements", sa.JSON(), nullable=False),
        sa.Column("adjudication", sa.JSON(), nullable=False),
        sa.Column("is_held_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "case_id", "label_version", name="uq_c1_reference_label_version"),
    )
    op.create_index(
        "ix_c1_reference_labels_project_id",
        "c1_reference_labels",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c1_reference_labels_case_id",
        "c1_reference_labels",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_c1_reference_labels_task_family",
        "c1_reference_labels",
        ["task_family"],
        unique=False,
    )
    op.create_index(
        "ix_c1_reference_labels_dataset_split",
        "c1_reference_labels",
        ["dataset_split"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_c1_reference_labels_dataset_split", table_name="c1_reference_labels")
    op.drop_index("ix_c1_reference_labels_task_family", table_name="c1_reference_labels")
    op.drop_index("ix_c1_reference_labels_case_id", table_name="c1_reference_labels")
    op.drop_index("ix_c1_reference_labels_project_id", table_name="c1_reference_labels")
    op.drop_table("c1_reference_labels")
