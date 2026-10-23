"""Server-side authorization and project access verification for Component 3.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Production hardening, server-side authorization, and end-to-end verification.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project
from app.shared.projects.service import get_project


def require_c3_active_user(
    current_user: Annotated[User, Depends(require_active_user)],
) -> User:
    """Ensure that the caller is an active user with an authorized platform role.

    Rejects unknown, unauthenticated, or unauthorized roles.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized role.",
        )
    return current_user


def verify_c3_project_access(
    project_id: str,
    current_user: User,
    db: Session,
) -> Project:
    """Verify that current_user has authorized access to project_id.

    ADMIN has access to all projects.
    USER has access only to projects they own.
    Fails closed with 404 (Not Found) to prevent project identifier enumeration.
    """
    if not project_id or not project_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project ID is required.",
        )
    clean_id = project_id.strip()
    return get_project(db, current_user, clean_id)


def verify_project_consistency(
    primary_project_id: str,
    *other_project_ids: str | None,
) -> None:
    """Validate that nested candidate, suite, or evidence project IDs match primary request project ID.

    Rejects mismatched or contradictory project scopes with HTTP 422.
    """
    clean_primary = primary_project_id.strip() if primary_project_id else ""
    for idx, candidate in enumerate(other_project_ids):
        if candidate is not None:
            clean_cand = candidate.strip()
            if clean_cand and clean_cand != clean_primary:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Inconsistent project identity in payload: '{clean_cand}' "
                        f"does not match request project scope '{clean_primary}'."
                    ),
                )
