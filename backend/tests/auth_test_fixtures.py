"""Shared authentication and project seeding utilities for tests.

Provides helpers to seed test users and projects into test sessions,
and configure dependency overrides for require_active_user.
"""

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)


def seed_test_admin(db: Session, user_id: int = 1) -> User:
    """Ensure an active ADMIN user exists in the session."""
    admin_user = db.get(User, user_id)
    if not admin_user:
        admin_user = User(
            id=user_id,
            name="Test Admin",
            email=f"admin-{user_id}@test.com",
            canonical_email=f"admin-{user_id}@test.com",
            password_hash="fake-hash",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.merge(admin_user)
        db.commit()
    return admin_user


def seed_test_projects(db: Session, project_ids: list[str], owner_id: int = 1) -> None:
    """Ensure project records exist in the session for project access checks."""
    for pid in project_ids:
        existing = db.get(Project, pid)
        if not existing:
            proj = Project(
                project_id=pid,
                owner_user_id=owner_id,
                name=f"Project {pid}",
                backend_base_url="http://localhost:8000",
                backend_health_url="http://localhost:8000/health",
                lifecycle=ProjectLifecycle.ACTIVE.value,
                connection_state=ProjectConnectionState.NOT_CHECKED.value,
            )
            db.merge(proj)
    db.commit()


class AutoSeedingTestClient(TestClient):
    """TestClient that automatically seeds valid referenced projects and authenticates."""

    def __init__(self, db_session: Session, user: User | None = None, *args, **kwargs):
        self.db_session = db_session
        self.test_user = user or seed_test_admin(db_session)
        super().__init__(app, *args, **kwargs)

    def request(self, method: str, url: str, *args, **kwargs):
        url_str = str(url)
        m = re.search(r"/projects/([^/]+)", url_str)
        if m:
            pid = m.group(1)
            # Only auto-seed if it does not look like a deliberate test for nonexistent project
            if (
                "nonexistent" not in pid
                and "notfound" not in pid
                and "missing" not in pid
            ):
                seed_test_projects(self.db_session, [pid], owner_id=self.test_user.id)
        return super().request(method, url, *args, **kwargs)


def make_authenticated_client(
    db_session: Session, user: User | None = None
) -> AutoSeedingTestClient:
    """Convenience helper to set up overrides and return an AutoSeedingTestClient."""
    admin_user = user or seed_test_admin(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_active_user] = lambda: admin_user
    return AutoSeedingTestClient(db_session, admin_user)
