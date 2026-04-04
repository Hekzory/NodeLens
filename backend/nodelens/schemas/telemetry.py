"""Pydantic schemas for telemetry API responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TelemetryPointRead(BaseModel):
    """Single telemetry data point."""

    time: datetime
    sensor_id: uuid.UUID
    value_numeric: float | None = None
    value_text: str | None = None


class TelemetrySeriesRead(BaseModel):
    """Time-series response for a sensor."""

    sensor_id: uuid.UUID
    points: list[TelemetryPointRead]
    count: int


class TelemetrySummary(BaseModel):
    """Aggregated summary for a sensor over a time window."""

    sensor_id: uuid.UUID
    count: int
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    first_time: datetime | None = None
    last_time: datetime | None = None


class TelemetryLatest(BaseModel):
    """Latest reading for a sensor."""

    sensor_id: uuid.UUID
    sensor_key: str
    sensor_name: str
    value_numeric: float | None = None
    value_text: str | None = None
    time: datetime | None = None


class DeviceTelemetryRead(BaseModel):
    """Latest readings from all sensors on a device."""

    device_id: uuid.UUID
    device_name: str
    readings: list[TelemetryLatest]
