"""SQLAlchemy model for persistent user-scoped model selections."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserModelSelection(Base):
    """User-owned authoritative model selection for the QA framework."""

    __tablename__ = "user_model_selections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    connection_type: Mapped[str] = mapped_column(
        String(32), default="local", nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(64), default="ollama", nullable=False
    )
    model_id: Mapped[str] = mapped_column(
        String(128), default="qwen3:4b", nullable=False
    )
    generation_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    last_test_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    last_test_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    @property
    def model(self) -> str:
        return self.model_id

    def to_config(self) -> dict[str, Any]:
        return {
            "connection_type": self.connection_type,
            "provider": self.provider,
            "model_id": self.model_id,
            "model": self.model_id,
            "generation_settings": self.generation_settings or {},
            "updated_at": self.updated_at,
        }
