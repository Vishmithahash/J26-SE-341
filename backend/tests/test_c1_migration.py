from pathlib import Path

from alembic.config import Config

from alembic import command
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)


def test_c1_models_metadata_registration():
    """Verify that Component 1 models are properly registered on SQLAlchemy Base metadata."""
    tables = C1ProjectConfigModel.metadata.tables
    assert "c1_project_configs" in tables
    assert "c1_suite_versions" in tables
    assert "c1_generation_runs" in tables
    assert "c1_execution_runs" in tables
    assert "c1_case_executions" in tables
    assert "c1_case_diagnoses" in tables
    assert "c1_corrections" in tables
    assert "c1_reference_labels" in tables

    # Check c1_reference_labels columns
    ref_table = tables["c1_reference_labels"]
    ref_expected_cols = {
        "id",
        "project_id",
        "case_id",
        "suite_id",
        "task_family",
        "dataset_split",
        "ground_truth_verdict",
        "ground_truth_cause",
        "ground_truth_code_locations",
        "valid_evidence_refs",
        "reviewer_id",
        "label_version",
        "disagreements",
        "adjudication",
        "is_held_out",
        "created_at",
    }
    assert ref_expected_cols.issubset({c.name for c in ref_table.columns})

    # Check columns in c1_project_configs

    config_table = tables["c1_project_configs"]
    expected_cols = {
        "id",
        "project_id",
        "version",
        "is_immutable",
        "agent_connection_ref",
        "tools",
        "requirements",
        "tool_constraints",
        "expectations",
        "synthetic_fixture_refs",
        "reset_capability",
        "trace_capabilities",
        "created_at",
        "updated_at",
    }
    actual_cols = {c.name for c in config_table.columns}
    assert expected_cols.issubset(actual_cols)

    # Check foreign key in c1_suite_versions
    suite_table = tables["c1_suite_versions"]
    fk_targets = [fk.target_fullname for fk in suite_table.foreign_keys]
    assert "c1_project_configs.id" in fk_targets

    # Check c1_generation_runs columns
    gen_table = tables["c1_generation_runs"]
    gen_expected_cols = {
        "id",
        "project_id",
        "config_id",
        "status",
        "request_payload",
        "summary",
        "candidates",
        "content_hash",
        "created_at",
    }
    assert gen_expected_cols.issubset({c.name for c in gen_table.columns})

    # Check c1_execution_runs columns
    exec_table = tables["c1_execution_runs"]
    exec_expected_cols = {
        "id",
        "project_id",
        "suite_id",
        "suite_version",
        "suite_version_id",
        "config_id",
        "status",
        "idempotency_key",
        "effective_config",
        "summary",
        "created_at",
    }
    assert exec_expected_cols.issubset({c.name for c in exec_table.columns})

    # Check c1_case_executions columns
    case_table = tables["c1_case_executions"]
    case_expected_cols = {
        "id",
        "run_id",
        "case_id",
        "attempt_number",
        "session_id",
        "readiness_status",
        "execution_status",
        "verdict",
        "trace_completeness",
        "resolved_expectations",
        "captured_events",
        "check_results",
    }
    assert case_expected_cols.issubset({c.name for c in case_table.columns})


def test_alembic_offline_migration_compatibility(tmp_path):
    """Verify that Alembic generates clean, valid SQL for both upgrade and downgrade offline."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    assert alembic_ini_path.exists(), f"alembic.ini not found at {alembic_ini_path}"

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Test offline SQL upgrade generation
    try:
        command.upgrade(alembic_cfg, "head", sql=True)
    except Exception as exc:
        raise AssertionError(f"Alembic offline upgrade failed: {exc}") from exc

    # Test offline SQL downgrade generation
    try:
        command.downgrade(alembic_cfg, "c1_0006:base", sql=True)
    except Exception as exc:
        raise AssertionError(f"Alembic offline downgrade failed: {exc}") from exc
