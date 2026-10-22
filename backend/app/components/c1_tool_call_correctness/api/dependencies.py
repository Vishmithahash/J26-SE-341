"""Authorization and project-scoping dependencies for Component 1.

Component: C1 Tool-Call Correctness Testing
Reuses shared authentication and project access services.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project
from app.shared.projects.service import get_project


def verify_project_access(
    project_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    x_project_id: str | None = Header(default=None, alias="X-Project-ID"),
) -> Project:
    """Authorize access to project-scoped C1 operations using shared platform policies.

    Enforces:
    1. Authenticated, active account dependency (require_active_user).
    2. Unknown or unauthorized platform roles are rejected with 403 Forbidden.
    3. Caller-supplied X-Project-ID header (if present) is validated as a consistency check;
       mismatches are rejected with 403 Forbidden. The header is not proof of authorization.
    4. Project existence and access enforcement via get_project:
       - USER may access only projects they own.
       - ADMIN follows the existing shared administrative access policy.
       - Missing or inaccessible projects fail closed with HTTP 404 (preventing enumeration).
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: role not authorized for C1 operations.",
        )

    if x_project_id is not None and x_project_id.strip() != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-project access denied: caller project context '{x_project_id}' "
                f"does not match route project '{project_id}'."
            ),
        )

    return get_project(db, current_user, project_id)
