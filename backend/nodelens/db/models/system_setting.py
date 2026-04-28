from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nodelens.db.base import Base


class SystemSetting(Base):
    """Sparse key/value store backing the System Settings UI.

    A row's presence means the operator has overridden the default declared in
    `nodelens.system_settings.registry.REGISTRY`. Missing rows fall back to the
    registry default (which is itself sourced from `nodelens.config.settings`).
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
