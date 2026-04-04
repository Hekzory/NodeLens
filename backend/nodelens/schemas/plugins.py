"""Pydantic schemas for plugin API responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PluginRead(BaseModel):
    """Full plugin representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plugin_type: str
    module_name: str
    display_name: str
    version: str
    is_active: bool
    created_at: datetime
    device_count: int = 0


class PluginUpdate(BaseModel):
    """Partial update for a plugin (currently only toggle)."""

    is_active: bool | None = None
    display_name: str | None = None
