"""Shared User SQLAlchemy model and role enumeration.

Component: Shared Platform Authentication & Authorization
"""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, Enum):
    """System-wide authorization roles."""

    ADMIN = "ADMIN"
    USER = "USER"


def normalize_email(email: str) -> str:
    """Normalize an email address into its canonical representation.

    Normalization policy:
    1. Strip leading and trailing whitespace.
    2. Convert all characters to lowercase.
    """
    return email.strip().lower()


class User(Base):
    """Shared persistent user model.

    Represents identity and global authorization roles (ADMIN or USER).
    Project-level permissions and research domain scoping are separate concerns.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        # Safe string representation that never reveals password_hash
        return (
            f"<User(id={self.id}, email={self.canonical_email!r}, "
            f"role={self.role.value!r}, is_active={self.is_active})>"
        )
