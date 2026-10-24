"""Service layer for authentication, user management, and authorization.

Component: Shared Platform Authentication & Authorization
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.schemas import UserSignupRequest, UserUpdateRequest
from app.shared.auth.security import (
    create_access_token,
    dummy_verify_password,
    hash_password,
    verify_password,
)


def register_user(db: Session, signup_data: UserSignupRequest) -> User:
    """Register a new user through the public sign-up endpoint.

    Guarantees:
    - Normalizes email to canonical form.
    - Strictly assigns UserRole.USER (never ADMIN, even for the first registered user).
    - Checks for existing accounts and handles concurrent duplicate registrations
      safely via database uniqueness constraints and transaction rollback.
    - Stores only the salted Argon2id password hash.
    """
    canonical_email = normalize_email(signup_data.email)

    existing_user = db.scalar(
        select(User).where(User.canonical_email == canonical_email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    pwd_hash = hash_password(signup_data.password)

    user = User(
        name=signup_data.name,
        email=signup_data.email,
        canonical_email=canonical_email,
        password_hash=pwd_hash,
        role=UserRole.USER,
        is_active=True,
    )

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    settings: Settings,
) -> tuple[User, str, int]:
    """Authenticate credentials and issue a bearer access token.

    Guarantees:
    - Constant-time dummy verification when user is unknown to mitigate timing enumeration.
    - Uniform generic HTTP 401 response for unknown email, bad password, and inactive accounts.
    - Issues short-lived JWT token containing user ID as stable 'sub' claim.
    """
    canonical_email = normalize_email(email)
    user = db.scalar(select(User).where(User.canonical_email == canonical_email))

    if user is None:
        dummy_verify_password(password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_in = create_access_token(user_id=user.id, settings=settings)
    return user, token, expires_in


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Retrieve user by primary identifier."""
    return db.get(User, user_id)


def list_users(
    db: Session,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[User], int]:
    """Retrieve paginated list of users and total count for administrative review."""
    total = db.scalar(select(func.count(User.id))) or 0
    query = (
        select(User)
        .order_by(User.id.asc())
        .limit(max(1, min(limit, 100)))
        .offset(max(0, offset))
    )
    users = list(db.scalars(query).all())
    return users, total


def provision_admin(
    db: Session,
    name: str,
    email: str,
    password: str,
) -> User:
    """Internal administrator provisioning (used exclusively by operator CLI).

    Guarantees:
    - Strictly internal; not exposed over public APIs.
    - Reuses canonical email normalization and Argon2id hashing.
    - Fails if the account already exists to prevent accidental password overwrites.
    """
    canonical_email = normalize_email(email)
    existing_user = db.scalar(
        select(User).where(User.canonical_email == canonical_email)
    )
    if existing_user is not None:
        raise ValueError(
            f"An account with email '{canonical_email}' already exists. "
            "To grant administrator access to an existing account, use the promote command."
        )

    pwd_hash = hash_password(password)
    user = User(
        name=name.strip(),
        email=email.strip(),
        canonical_email=canonical_email,
        password_hash=pwd_hash,
        role=UserRole.ADMIN,
        is_active=True,
    )

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"An account with email '{canonical_email}' already exists."
        ) from None


def promote_user_to_admin(db: Session, email: str) -> tuple[User, bool]:
    """Explicitly promote an existing user account to ADMIN.

    Guarantees:
    - Never resets or modifies the existing user's password.
    - Returns (user, was_already_admin).
    """
    canonical_email = normalize_email(email)
    user = db.scalar(select(User).where(User.canonical_email == canonical_email))
    if user is None:
        raise ValueError(f"No account found with email '{canonical_email}'.")

    if user.role == UserRole.ADMIN:
        return user, True

    user.role = UserRole.ADMIN
    db.commit()
    db.refresh(user)
    return user, False


def update_user_profile(
    db: Session,
    user: User,
    update_data: UserUpdateRequest,
) -> User:
    """Update display name for the authenticated user."""
    user.name = update_data.name
    db.commit()
    db.refresh(user)
    return user


def change_user_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Verify current password and update to new password.

    Guarantees:
    - Verifies current password with Argon2id before updating.
    - Never logs, returns, or stores plaintext passwords.
    - Rehashes new password using standard Argon2id configuration.
    """
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)


def set_user_active_status(
    db: Session,
    admin_user: User,
    target_user_id: int,
    is_active: bool,
) -> User:
    """Update active status of a user account.

    Guarantees:
    - Target user must exist (HTTP 404 if not found).
    - An administrator cannot deactivate their own active account (HTTP 400).
    - Returns updated User object.
    """
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if target.id == admin_user.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    target.is_active = is_active
    db.commit()
    db.refresh(target)
    return target
