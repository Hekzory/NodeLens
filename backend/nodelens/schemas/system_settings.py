"""Pydantic models for the System Settings API.

The list response merges DB values with registry metadata so the frontend can
render the form without a second round-trip. Inputs are loose (``Any``)
because the registry knows the typing — the service layer coerces and
validates per key.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SystemSettingRead(BaseModel):
    """One registered setting plus its current value."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    group: str
    value_type: str
    value: Any
    default: Any
    is_default: bool
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    requires_restart: bool
    affects_services: list[str] = []
    help: str
    updated_at: datetime | None = None


class SystemSettingsUpdate(BaseModel):
    """Bulk PATCH body — keys map directly to registry keys."""

    model_config = ConfigDict(extra="forbid")

    updates: dict[str, Any]


class SystemSettingsUpdateResponse(BaseModel):
    """PATCH response — updated entries plus the keys requiring restart."""

    model_config = ConfigDict(extra="forbid")

    updated: list[SystemSettingRead]
    requires_restart_keys: list[str]
