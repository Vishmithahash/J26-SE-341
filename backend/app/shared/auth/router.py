"""FastAPI routers for shared authentication and administrator operations.

Endpoints:
- POST /api/v1/auth/signup: Public user registration (always creates USER)
- POST /api/v1/auth/login: Common credentials login (returns short-lived JWT)
- GET /api/v1/auth/me: Retrieve current authenticated identity
- GET /api/v1/admin/users: Administrator-only paginated user listing
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.shared.auth.dependencies import (
    require_active_user,
    require_admin,
)
from app.shared.auth.models import User
from app.shared.auth.schemas import (
    PasswordChangeRequest,
    TokenResponse,
    UserListResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.shared.auth.security import login_rate_limiter
from app.shared.auth.service import (
    authenticate_user,
    change_user_password,
    list_users,
    register_user,
    set_user_active_status,
    update_user_profile,
)


class AuthSafeRoute(APIRoute):
    """Custom APIRoute ensuring authentication request-validation errors are sanitized.

    Guarantees:
    - Never echoes raw request bodies, submitted passwords, or internal exception context.
    - Preserves field locations and clean validation messages.
    """

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                sanitized_errors = []
                for err in exc.errors():
                    loc = [str(p) for p in err.get("loc", ["body"])]
                    loc_str = ".".join(loc).lower()
                    msg = err.get("msg", "Validation error")

                    # Sanitize password error messages to prevent echoing input values
                    if "password" in loc_str:
                        err_type = err.get("type", "")
                        if "string_too_short" in err_type or "min_length" in err_type:
                            msg = "Password must be at least 8 characters."
                        elif "string_too_long" in err_type or "max_length" in err_type:
                            msg = "Password must not exceed 128 characters."
                        else:
                            msg = "Invalid password value or format."

                    # Suppress potential secret leak patterns in error message
                    if any(
                        s in msg.lower()
                        for s in ("secret", "token", "hash", "argon2", "key")
                    ):
                        msg = "Invalid input format."

                    sanitized_errors.append(
                        {
                            "loc": loc,
                            "msg": msg,
                            "type": err.get("type", "value_error"),
                        }
                    )
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content={"detail": sanitized_errors},
                )

        return custom_handler


router = APIRouter(route_class=AuthSafeRoute)
auth_router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Shared: Authentication"],
    route_class=AuthSafeRoute,
)
admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Shared: Administration"],
    route_class=AuthSafeRoute,
)


@auth_router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Public User Registration",
    description=(
        "Registers a new account. Always assigns the USER role. "
        "Strictly forbids injected privilege fields. "
        "Passwords require at least 8 characters."
    ),
)
def signup(
    signup_data: UserSignupRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    user = register_user(db=db, signup_data=signup_data)
    return UserResponse.model_validate(user)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Credentials Login",
    description=(
        "Common login endpoint for both USER and ADMIN roles. "
        "Returns a short-lived signed bearer access token."
    ),
)
def login(
    login_data: UserLoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    # Derive rate limiter key based on client IP
    client_ip = request.client.host if request.client else "unknown"
    login_rate_limiter.check_rate_limit(client_ip)

    try:
        user, access_token, expires_in = authenticate_user(
            db=db,
            email=login_data.email,
            password=login_data.password,
            settings=settings,
        )
    except Exception:
        login_rate_limiter.record_failure(client_ip)
        raise

    login_rate_limiter.reset(client_ip)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@auth_router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current Authenticated User",
    description="Returns the profile and role of the currently authenticated user.",
)
def get_me(
    current_user: Annotated[User, Depends(require_active_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@auth_router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Profile",
    description="Updates the current authenticated user's profile display name.",
)
def update_me(
    update_data: UserUpdateRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    updated = update_user_profile(db=db, user=current_user, update_data=update_data)
    return UserResponse.model_validate(updated)


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Verifies the current password and updates to a new password.",
)
def change_password(
    data: PasswordChangeRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    change_user_password(
        db=db,
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    return {"message": "Password updated successfully."}
@admin_router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Users (Administrator Only)",
    description=(
        "Returns a paginated list of registered users. "
        "Requires authenticated caller with ADMIN role."
    ),
)
def get_users(
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> UserListResponse:
    items, total = list_users(db=db, limit=limit, offset=offset)
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Active Status (Administrator Only)",
    description=(
        "Activate or deactivate a user account. "
        "Requires authenticated caller with ADMIN role. "
        "Administrators cannot deactivate their own account."
    ),
)
def update_user_status(
    user_id: int,
    data: UserStatusUpdateRequest,
    admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    target = set_user_active_status(
        db=db,
        admin_user=admin_user,
        target_user_id=user_id,
        is_active=data.is_active,
    )
    return UserResponse.model_validate(target)


@admin_router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Account (Administrator Only)",
)
def update_user_account(
    user_id: int,
    data: UserStatusUpdateRequest,
    admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    target = set_user_active_status(
        db=db,
        admin_user=admin_user,
        target_user_id=user_id,
        is_active=data.is_active,
    )
    return UserResponse.model_validate(target)


# Register sub-routers into top-level shared router
router.include_router(auth_router)
router.include_router(admin_router)
