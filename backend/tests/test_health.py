import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

# Ensure isolated test settings with an unmistakably fake database URL
# BEFORE importing application modules that read configuration.
TEST_DATABASE_URL = "postgresql://test_fake_user:fake_secret_password@fake-test-host.local:5432/test_db?sslmode=require"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import Settings
from app.database import get_db, normalize_database_url
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Agentic AI QA Framework API",
        "status": "running",
    }


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_db_success(client):
    mock_session = MagicMock(spec=Session)
    mock_scalar = MagicMock()
    mock_scalar.scalar.return_value = 1
    mock_session.execute.return_value = mock_scalar

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


def test_health_db_failure_scalar_mismatch(client):
    mock_session = MagicMock(spec=Session)
    mock_scalar = MagicMock()
    mock_scalar.scalar.return_value = 0
    mock_session.execute.return_value = mock_scalar

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unavailable"}


def test_health_db_failure_exception_suppresses_credentials(client):
    mock_session = MagicMock(spec=Session)
    secret_leak = "leak_sensitive_pass_12345"
    mock_session.execute.side_effect = OperationalError(
        f"connection failed with secret {secret_leak}",
        params=None,
        orig=Exception(f"raw exception containing {secret_leak}"),
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unavailable"}
    assert secret_leak not in response.text
    assert "fake_secret_password" not in response.text


def test_config_empty_database_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="")
    err_str = str(exc_info.value)
    assert "DATABASE_URL must not be empty" in err_str


def test_config_malformed_database_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL=":::not_a_valid_url:::")
    err_str = str(exc_info.value)
    assert "DATABASE_URL is malformed" in err_str


def test_config_unsupported_scheme():
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="mysql+pymysql://user:pass@host/db")
    err_str = str(exc_info.value)
    assert "Unsupported database scheme" in err_str
    assert "user:pass" not in err_str


def test_config_insecure_sslmode():
    for insecure in ["disable", "allow", "prefer"]:
        with pytest.raises(ValidationError) as exc_info:
            Settings(DATABASE_URL=f"postgresql://user:pass@host/db?sslmode={insecure}")
        err_str = str(exc_info.value)
        assert "Insecure sslmode" in err_str
        assert "pass" not in err_str


def test_normalize_database_url_variations():
    # Test postgresql:// normalized to postgresql+psycopg://
    url1 = normalize_database_url("postgresql://u:p@host/db")
    assert url1.drivername == "postgresql+psycopg"
    assert url1.query.get("sslmode") == "require"

    # Test postgres:// normalized
    url2 = normalize_database_url("postgres://u:p@host/db?sslmode=verify-full")
    assert url2.drivername == "postgresql+psycopg"
    assert url2.query.get("sslmode") == "verify-full"

    # Test SecretStr and query params preserved
    url3 = normalize_database_url(
        SecretStr(
            "postgresql+psycopg://u:p@host/db?sslmode=verify-ca&channel_binding=require"
        )
    )
    assert url3.drivername == "postgresql+psycopg"
    assert url3.query.get("sslmode") == "verify-ca"
    assert url3.query.get("channel_binding") == "require"
