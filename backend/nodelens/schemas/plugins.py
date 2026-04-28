"""Pydantic schemas for plugin API responses."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginRead(BaseModel):
    """Full plugin representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plugin_type: str
    module_name: str
    display_name: str
    description: str | None = None
    version: str
    is_active: bool
    created_at: datetime
    device_count: int = 0


class PluginUpdate(BaseModel):
    """Partial update for a plugin (currently only toggle)."""

    is_active: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=255)


# ── Per-plugin configuration ─────────────────────────────────────


class PluginConfigFieldRead(BaseModel):
    """One config field plus its current effective value.

    Secret fields never echo the real value: ``value`` is a masked sentinel
    when set, ``None`` when unset, and ``default`` is also nulled.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    group: str
    value_type: Literal["int", "float", "bool", "string", "secret"]
    value: Any
    default: Any
    is_default: bool
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    requires_restart: bool = False
    help: str = ""


class PluginConfigRead(BaseModel):
    """Full config payload for a plugin."""

    model_config = ConfigDict(extra="forbid")

    plugin_id: uuid.UUID
    config_version: int
    fields: list[PluginConfigFieldRead]


class PluginConfigUpdate(BaseModel):
    """Bulk PATCH body — keys map to schema fields."""

    model_config = ConfigDict(extra="forbid")

    updates: dict[str, Any]


class PluginConfigUpdateResponse(BaseModel):
    """PATCH response — full re-loaded config plus restart hints."""

    model_config = ConfigDict(extra="forbid")

    config: PluginConfigRead
    requires_restart_keys: list[str]
