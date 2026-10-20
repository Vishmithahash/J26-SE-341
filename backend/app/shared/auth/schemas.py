"""Pydantic schemas and contracts for shared authentication and authorization.

Component: Shared Platform Authentication & Authorization
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.shared.auth.models import UserRole

# Standard RFC 5322 compatible email pattern
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def _validate_email_format(v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Email cannot be empty.")
    if len(cleaned) > 255:
        raise ValueError("Email exceeds maximum allowed length of 255 characters.")
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email format.")
    return cleaned


EmailField = Annotated[str, AfterValidator(_validate_email_format)]


class UserSignupRequest(BaseModel):
    """Public sign-up request contract.

    Strictly forbids unexpected or injected fields (e.g., role, is_admin, is_active).
    Passwords must be at least 15 characters and up to 128 characters.
    Spaces and Unicode are permitted; no silent transformation or truncation is applied.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=255, description="User display name"
    )
    email: EmailField = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=15,
        max_length=128,
        description="Password (min 15 chars, max 128 chars, Unicode/spaces permitted)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or whitespace only.")
        return stripped


class UserLoginRequest(BaseModel):
    """Credentials login request contract.

    Strictly forbids unexpected fields.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailField = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Account password",
    )


class UserResponse(BaseModel):
    """Safe public user representation.

    Never exposes password hashes or internal sensitive fields.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at_utc: datetime


class TokenResponse(BaseModel):
    """Bearer token issuance response contract."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserListResponse(BaseModel):
    """Paginated list of users for administrator inspection."""

    model_config = ConfigDict(extra="forbid")

    items: list[UserResponse]
    total: int
    limit: int
    offset: int
