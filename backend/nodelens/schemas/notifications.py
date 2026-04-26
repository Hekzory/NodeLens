"""Pydantic schemas for notification channels and rule-channel links."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    plugin_id: uuid.UUID
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class NotificationChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    plugin_id: uuid.UUID | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class NotificationChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plugin_id: uuid.UUID
    plugin_module_name: str | None = None
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RuleChannelsUpdate(BaseModel):
    """Body for PUT /api/alerts/rules/{id}/channels — replaces the link set."""

    channel_ids: list[uuid.UUID] = Field(default_factory=list)
