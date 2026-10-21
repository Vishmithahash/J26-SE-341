"""C4 test authentication and database seeding utilities.

Component: C4 Policy-Aware Safety and Prompt-Injection Testing
Scope: Test utilities for C4-owned backend tests.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.main import app
from app.shared.auth.models import User, UserRole
from app.shared.auth.security import create_access_token
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

C4_TEST_AUTH_SECRET = "c4-test-secret-key-at-least-32-chars-long"

STANDARD_C4_TEST_PROJECTS = [
    "test-project-alpha",
    "proj-api-test",
    "proj-p3-api",
    "proj-idem",
    "proj-p5-api",
    "proj-p6-api",
]


def create_authenticated_c4_client(
    db_session: Session,
    project_ids: list[str] | None = None,
    user_role: UserRole = UserRole.ADMIN,
    user_id: int = 1,
) -> TestClient:
    """Create a TestClient with authenticated JWT bearer header and seeded projects."""
    test_settings = Settings(auth_secret_key=C4_TEST_AUTH_SECRET)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = lambda: db_session

    user = User(
        id=user_id,
        name=f"C4 Test {user_role.value}",
        email=f"c4-user-{user_id}@example.com",
        canonical_email=f"c4-user-{user_id}@example.com",
        password_hash="fake-hash",
        role=user_role,
        is_active=True,
    )
    db_session.merge(user)

    target_projects = project_ids or STANDARD_C4_TEST_PROJECTS
    for pid in target_projects:
        proj = Project(
            project_id=pid,
            owner_user_id=user_id,
            name=f"Project {pid}",
            domain="e-commerce",
            environment="development",
            backend_base_url="http://localhost:8000",
            backend_health_url="http://localhost:8000/health",
            configuration_version=1,
            lifecycle=ProjectLifecycle.ACTIVE.value,
            connection_state=ProjectConnectionState.NOT_CHECKED.value,
        )
        db_session.merge(proj)
    db_session.commit()

    token, _ = create_access_token(user_id, test_settings)

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
