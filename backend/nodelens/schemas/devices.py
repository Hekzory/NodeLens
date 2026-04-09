"""Pydantic schemas for device API responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SensorBrief(BaseModel):
    """Minimal sensor info when nested inside a device response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    unit: str | None = None
    value_type: str


class DeviceRead(BaseModel):
    """Device list item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plugin_id: uuid.UUID
    external_id: str
    name: str
    location: str | None = None
    is_online: bool = False
    last_seen: datetime | None = None
    created_at: datetime
    sensor_count: int = 0


class DeviceDetail(BaseModel):
    """Device with nested sensors."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plugin_id: uuid.UUID
    external_id: str
    name: str
    location: str | None = None
    is_online: bool = False
    last_seen: datetime | None = None
    created_at: datetime
    sensors: list[SensorBrief] = []


class SensorRead(BaseModel):
    """Full sensor representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    key: str
    name: str
    unit: str | None = None
    value_type: str
    created_at: datetime
