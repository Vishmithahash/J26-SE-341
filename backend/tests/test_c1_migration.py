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


def test_alembic_offline_migration_compatibility(tmp_path):
    """Verify that Alembic generates clean, valid SQL for both upgrade and downgrade offline."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    assert alembic_ini_path.exists(), f"alembic.ini not found at {alembic_ini_path}"

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Test offline SQL upgrade generation
    # Alembic in offline mode prints or outputs SQL buffer
    # We verify that command.upgrade does not raise exceptions
    try:
        command.upgrade(alembic_cfg, "head", sql=True)
    except Exception as exc:
        raise AssertionError(f"Alembic offline upgrade failed: {exc}") from exc

    # Test offline SQL downgrade generation
    try:
        command.downgrade(alembic_cfg, "c1_0001:base", sql=True)
    except Exception as exc:
        raise AssertionError(f"Alembic offline downgrade failed: {exc}") from exc
