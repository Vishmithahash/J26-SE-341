"""create_c3_persistence_tables

Revision ID: e75342624f8c
Revises:
Create Date: 2026-10-19 11:30:16.546169

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e75342624f8c"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema by creating C3 persistence tables."""
    # 1. c3_suites
    op.create_table(
        "c3_suites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suite_id", sa.String(length=128), nullable=False),
        sa.Column("suite_digest", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("tool_id", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("generator_version", sa.String(length=32), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("adapter_manifest_snapshot", sa.JSON(), nullable=False),
        sa.Column("task_fixture_metadata_snapshot", sa.JSON(), nullable=False),
        sa.Column("recovery_contract_snapshot", sa.JSON(), nullable=False),
        sa.Column("suite_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_digest", name="uq_c3_suites_suite_digest"),
    )
    op.create_index("ix_c3_suites_suite_id", "c3_suites", ["suite_id"], unique=False)
    op.create_index(
        "ix_c3_suites_suite_digest", "c3_suites", ["suite_digest"], unique=True
    )
    op.create_index(
        "ix_c3_suites_project_id", "c3_suites", ["project_id"], unique=False
    )

    # 2. c3_cases
    op.create_table(
        "c3_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("suite_digest", sa.String(length=64), nullable=False),
        sa.Column("case_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("case_family_id", sa.String(length=128), nullable=False),
        sa.Column("fault_family", sa.String(length=64), nullable=False),
        sa.Column("effect_phase", sa.String(length=64), nullable=False),
        sa.Column("interception_hook", sa.String(length=64), nullable=False),
        sa.Column("target_tool_id", sa.String(length=128), nullable=False),
        sa.Column("case_order", sa.Integer(), nullable=False),
        sa.Column("case_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["suite_digest"], ["c3_suites.suite_digest"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "suite_digest", "case_id", name="uq_c3_cases_suite_digest_case_id"
        ),
    )
    op.create_index("ix_c3_cases_case_id", "c3_cases", ["case_id"], unique=False)
    op.create_index(
        "ix_c3_cases_suite_digest", "c3_cases", ["suite_digest"], unique=False
    )
    op.create_index(
        "ix_c3_cases_case_fingerprint", "c3_cases", ["case_fingerprint"], unique=False
    )
    op.create_index("ix_c3_cases_project_id", "c3_cases", ["project_id"], unique=False)
    op.create_index(
        "ix_c3_cases_fault_family", "c3_cases", ["fault_family"], unique=False
    )
    op.create_index(
        "ix_c3_cases_effect_phase", "c3_cases", ["effect_phase"], unique=False
    )
    op.create_index(
        "ix_c3_cases_project_suite",
        "c3_cases",
        ["project_id", "suite_digest"],
        unique=False,
    )

    # 3. c3_executions
    op.create_table(
        "c3_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.String(length=128), nullable=False),
        sa.Column("suite_digest", sa.String(length=64), nullable=False),
        sa.Column("suite_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("target_mode", sa.String(length=32), nullable=False),
        sa.Column("caller_identity", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "planned_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "executed_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "blocked_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "unsupported_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "cancelled_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "error_cases_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("halt_reason", sa.Text(), nullable=True),
        sa.Column("manifest_snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", name="uq_c3_executions_execution_id"),
    )
    op.create_index(
        "ix_c3_executions_execution_id",
        "c3_executions",
        ["execution_id"],
        unique=True,
    )
    op.create_index(
        "ix_c3_executions_suite_digest",
        "c3_executions",
        ["suite_digest"],
        unique=False,
    )
    op.create_index(
        "ix_c3_executions_project_id", "c3_executions", ["project_id"], unique=False
    )
    op.create_index(
        "ix_c3_executions_target_mode", "c3_executions", ["target_mode"], unique=False
    )
    op.create_index(
        "ix_c3_executions_status", "c3_executions", ["status"], unique=False
    )
    op.create_index(
        "ix_c3_executions_project_status",
        "c3_executions",
        ["project_id", "status"],
        unique=False,
    )

    # 4. c3_matched_pairs
    op.create_table(
        "c3_matched_pairs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pair_id", sa.String(length=128), nullable=False),
        sa.Column("execution_id", sa.String(length=128), nullable=True),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=128),
            nullable=False,
            comment="Documented opaque reference to shared run record",
        ),
        sa.Column("clean_trial_id", sa.String(length=128), nullable=False),
        sa.Column("fault_trial_id", sa.String(length=128), nullable=False),
        sa.Column("readiness_status", sa.String(length=32), nullable=False),
        sa.Column("clean_qualification", sa.String(length=32), nullable=False),
        sa.Column("exposure_status", sa.String(length=32), nullable=False),
        sa.Column("exposure_assessed", sa.Boolean(), nullable=False),
        sa.Column("cleanup_status", sa.String(length=32), nullable=False),
        sa.Column("clean_execution_status", sa.String(length=32), nullable=False),
        sa.Column("fault_execution_status", sa.String(length=32), nullable=False),
        sa.Column("evidence_complete", sa.Boolean(), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair_id", name="uq_c3_matched_pairs_pair_id"),
    )
    op.create_index(
        "ix_c3_matched_pairs_pair_id", "c3_matched_pairs", ["pair_id"], unique=True
    )
    op.create_index(
        "ix_c3_matched_pairs_execution_id",
        "c3_matched_pairs",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        "ix_c3_matched_pairs_case_id", "c3_matched_pairs", ["case_id"], unique=False
    )
    op.create_index(
        "ix_c3_matched_pairs_project_id",
        "c3_matched_pairs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_c3_matched_pairs_run_id", "c3_matched_pairs", ["run_id"], unique=False
    )
    op.create_index(
        "ix_c3_matched_pairs_clean_qualification",
        "c3_matched_pairs",
        ["clean_qualification"],
        unique=False,
    )
    op.create_index(
        "ix_c3_matched_pairs_exposure_status",
        "c3_matched_pairs",
        ["exposure_status"],
        unique=False,
    )
    op.create_index(
        "ix_c3_matched_pairs_fault_execution_status",
        "c3_matched_pairs",
        ["fault_execution_status"],
        unique=False,
    )
    op.create_index(
        "ix_c3_pairs_project_case",
        "c3_matched_pairs",
        ["project_id", "case_id"],
        unique=False,
    )
    op.create_index(
        "ix_c3_pairs_execution", "c3_matched_pairs", ["execution_id"], unique=False
    )

    # 5. c3_evaluations
    op.create_table(
        "c3_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_id", sa.String(length=128), nullable=False),
        sa.Column("pair_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("evaluator_version", sa.String(length=32), nullable=False),
        sa.Column("rule_set_version", sa.String(length=32), nullable=False),
        sa.Column("evaluation_status", sa.String(length=32), nullable=False),
        sa.Column("recovery_verdict", sa.String(length=32), nullable=True),
        sa.Column("first_violated_rule", sa.String(length=64), nullable=True),
        sa.Column("actor_attribution", sa.String(length=64), nullable=False),
        sa.Column(
            "inputs_digest",
            sa.String(length=64),
            nullable=False,
            comment="Deterministic SHA-256 digest of matched evidence + C2 facts inputs",
        ),
        sa.Column("c2_facts_provenance_snapshot", sa.JSON(), nullable=False),
        sa.Column("rule_results_snapshot", sa.JSON(), nullable=False),
        sa.Column("evaluation_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pair_id"], ["c3_matched_pairs.pair_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", name="uq_c3_evaluations_evaluation_id"),
        sa.UniqueConstraint(
            "pair_id",
            "evaluator_version",
            "rule_set_version",
            "inputs_digest",
            name="uq_c3_evaluations_idempotent_inputs",
        ),
    )
    op.create_index(
        "ix_c3_evaluations_evaluation_id",
        "c3_evaluations",
        ["evaluation_id"],
        unique=True,
    )
    op.create_index(
        "ix_c3_evaluations_pair_id", "c3_evaluations", ["pair_id"], unique=False
    )
    op.create_index(
        "ix_c3_evaluations_case_id", "c3_evaluations", ["case_id"], unique=False
    )
    op.create_index(
        "ix_c3_evaluations_project_id", "c3_evaluations", ["project_id"], unique=False
    )
    op.create_index(
        "ix_c3_evaluations_evaluator_version",
        "c3_evaluations",
        ["evaluator_version"],
        unique=False,
    )
    op.create_index(
        "ix_c3_evaluations_rule_set_version",
        "c3_evaluations",
        ["rule_set_version"],
        unique=False,
    )
    op.create_index(
        "ix_c3_evaluations_evaluation_status",
        "c3_evaluations",
        ["evaluation_status"],
        unique=False,
    )
    op.create_index(
        "ix_c3_evaluations_recovery_verdict",
        "c3_evaluations",
        ["recovery_verdict"],
        unique=False,
    )
    op.create_index(
        "ix_c3_eval_project_verdict",
        "c3_evaluations",
        ["project_id", "recovery_verdict"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema by dropping C3 persistence tables in reverse order."""
    op.drop_table("c3_evaluations")
    op.drop_table("c3_matched_pairs")
    op.drop_table("c3_executions")
    op.drop_table("c3_cases")
    op.drop_table("c3_suites")
