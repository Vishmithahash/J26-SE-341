"""Shared authentication and role-based authorization package."""

from app.shared.auth.dependencies import (
    get_current_user,
    require_active_user,
    require_admin,
)
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.router import router

__all__ = [
    "User",
    "UserRole",
    "get_current_user",
    "normalize_email",
    "require_active_user",
    "require_admin",
    "router",
]
