"""FastAPI dependencies for shared authentication and role-based authorization.

Component: Shared Platform Authentication & Authorization
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.shared.auth.models import User, UserRole
from app.shared.auth.security import decode_access_token

# HTTP Bearer scheme with automatic error suppression so we can provide consistent RFC-compliant 401 responses
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Extract, verify token, and load current user record from the database.

    Enforces that current role and active status are loaded directly from the database,
    never relying on an untrusted token role claim as authorization authority.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token, settings)

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure that the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_admin(
    current_user: Annotated[User, Depends(require_active_user)],
) -> User:
    """Ensure that the authenticated user possesses the ADMIN role.

    Anonymous requests return HTTP 401 (via upstream get_current_user).
    Authenticated non-admin users return HTTP 403 Forbidden.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user
