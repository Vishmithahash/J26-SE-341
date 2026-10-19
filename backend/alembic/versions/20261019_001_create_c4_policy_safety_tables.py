"""Create C4 policy safety tables

Revision ID: 20261019_001_c4
Revises: None
Create Date: 2026-10-19 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261019_001_c4"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. c4_artifacts
    op.create_table(
        "c4_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("artifact_kind", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "artifact_id", "version", name="uq_c4_artifacts_proj_id_ver"
        ),
    )
    op.create_index(
        op.f("ix_c4_artifacts_project_id"), "c4_artifacts", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_c4_artifacts_artifact_id"),
        "c4_artifacts",
        ["artifact_id"],
        unique=False,
    )

    # 2. c4_candidate_rules
    op.create_table(
        "c4_candidate_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False, default=1),
        sa.Column("policy_family", sa.String(length=64), nullable=False),
        sa.Column(
            "review_status", sa.String(length=32), nullable=False, default="DRAFT"
        ),
        sa.Column("rule_data", sa.JSON(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "rule_id",
            "rule_version",
            name="uq_c4_candidate_rules_proj_id_ver",
        ),
    )
    op.create_index(
        op.f("ix_c4_candidate_rules_project_id"),
        "c4_candidate_rules",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_candidate_rules_rule_id"),
        "c4_candidate_rules",
        ["rule_id"],
        unique=False,
    )

    # 3. c4_policy_contracts
    op.create_table(
        "c4_policy_contracts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "lifecycle_state", sa.String(length=32), nullable=False, default="DRAFT"
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("rules_data", sa.JSON(), nullable=False),
        sa.Column("referenced_artifact_versions", sa.JSON(), nullable=False),
        sa.Column("acceptance_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "contract_id", "version", name="uq_c4_contracts_proj_id_ver"
        ),
    )
    op.create_index(
        op.f("ix_c4_policy_contracts_project_id"),
        "c4_policy_contracts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_policy_contracts_contract_id"),
        "c4_policy_contracts",
        ["contract_id"],
        unique=False,
    )

    # 4. c4_evaluation_findings
    op.create_table(
        "c4_evaluation_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("finding_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("violation_stage", sa.String(length=64), nullable=True),
        sa.Column("finding_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", name="uq_c4_evaluation_findings_finding_id"),
    )
    op.create_index(
        op.f("ix_c4_evaluation_findings_finding_id"),
        "c4_evaluation_findings",
        ["finding_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_c4_evaluation_findings_project_id"),
        "c4_evaluation_findings",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_evaluation_findings_case_id"),
        "c4_evaluation_findings",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_c4_evaluation_findings_run_id"),
        "c4_evaluation_findings",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("c4_evaluation_findings")
    op.drop_table("c4_policy_contracts")
    op.drop_table("c4_candidate_rules")
    op.drop_table("c4_artifacts")
