"""Create C4 Phase 2 domain bindings, generation batches, and test cases tables

Revision ID: 20261019_002_c4
Revises: 20261019_001_c4
Create Date: 2026-10-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261019_002_c4"
down_revision: str | Sequence[str] | None = "20261019_001_c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. c4_domain_bindings
    op.create_table(
        "c4_domain_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("binding_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "binding_id",
            "version",
            name="uq_c4_domain_bindings_proj_id_ver",
        ),
    )
    op.create_index(
        op.f("ix_c4_domain_bindings_project_id"),
        "c4_domain_bindings",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_domain_bindings_binding_id"),
        "c4_domain_bindings",
        ["binding_id"],
        unique=False,
    )

    # 2. c4_generation_batches
    op.create_table(
        "c4_generation_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("config_digest", sa.String(length=64), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            name="uq_c4_generation_batches_batch_id",
        ),
    )
    op.create_index(
        op.f("ix_c4_generation_batches_batch_id"),
        "c4_generation_batches",
        ["batch_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_c4_generation_batches_project_id"),
        "c4_generation_batches",
        ["project_id"],
        unique=False,
    )

    # 3. c4_test_cases
    op.create_table(
        "c4_test_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=True),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("test_kind", sa.String(length=64), nullable=False),
        sa.Column(
            "lifecycle_state", sa.String(length=32), nullable=False, server_default="DRAFT"
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("case_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "case_id",
            "case_version",
            name="uq_c4_test_cases_proj_id_ver",
        ),
    )
    op.create_index(
        op.f("ix_c4_test_cases_project_id"),
        "c4_test_cases",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_test_cases_case_id"),
        "c4_test_cases",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_test_cases_batch_id"),
        "c4_test_cases",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_test_cases_rule_id"),
        "c4_test_cases",
        ["rule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("c4_test_cases")
    op.drop_table("c4_generation_batches")
    op.drop_table("c4_domain_bindings")
