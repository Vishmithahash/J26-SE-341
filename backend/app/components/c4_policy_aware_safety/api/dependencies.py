"""Authorization and project-scoping dependencies for Component 4.

Component: C4 Policy-Aware Safety and Prompt-Injection Testing
Strict Ownership Boundaries: C4-owned backend authorization module.
Reuses shared authentication and project access services without modifying them.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project
from app.shared.projects.service import get_project


def get_authorized_c4_project(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Project:
    """Enforce platform authentication, active account, and project authorization.

    Access Policy:
    - Unauthenticated callers -> HTTP 401 Unauthorized (via require_active_user)
    - Inactive accounts -> HTTP 401 Unauthorized (via require_active_user)
    - Unsupported platform roles -> HTTP 403 Forbidden
    - Standard USER accounts -> Access allowed only if user owns the project (via get_project -> HTTP 404)
    - ADMIN accounts -> Platform-wide access allowed to all projects (via get_project)
    - Inaccessible or non-existent projects fail closed with HTTP 404 to prevent ID enumeration.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: role not authorized for C4 operations.",
        )

    # get_project verifies project existence and enforces user ownership (or ADMIN bypass).
    # Fails closed with HTTP 404 if project is missing or owned by another user.
    return get_project(db, current_user, project_id)
