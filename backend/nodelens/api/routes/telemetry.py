"""Telemetry query endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens.api.deps import get_db
from nodelens.db.models import Device, Sensor, TelemetryRecord
from nodelens.schemas.telemetry import (
    DeviceTelemetryRead,
    TelemetryLatest,
    TelemetryPointRead,
    TelemetrySeriesRead,
    TelemetrySummary,
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# Whitelist of allowed time_bucket intervals to prevent injection.
_ALLOWED_INTERVALS: dict[str, str] = {
    "10s": "10 seconds",
    "1m": "1 minute",
    "15m": "15 minutes",
    "30m": "30 minutes",
    "1h": "1 hour",
    "6h": "6 hours",
    "12h": "12 hours",
    "1d": "1 day",
}


@router.get("/{sensor_id}", response_model=TelemetrySeriesRead)
async def get_telemetry_series(
    sensor_id: uuid.UUID,
    start: datetime | None = Query(default=None, description="Start of time range (ISO 8601)"),
    end: datetime | None = Query(default=None, description="End of time range (ISO 8601)"),
    limit: int = Query(default=5000, ge=1, le=50000, description="Max points to return"),
    interval: str | None = Query(default=None, description="Aggregation interval (1m, 15m, 30m, 1h, 6h, 12h, 1d)"),
    db: AsyncSession = Depends(get_db),
):
    """Get time-series data for a sensor within a time range.

    When ``interval`` is set, points are aggregated into time buckets using
    TimescaleDB ``time_bucket`` and averaged.
    """
    sensor = await db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    if end is None:
        end = datetime.now(UTC)
    if start is None:
        start = end - timedelta(hours=1)

    if interval and interval not in _ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Allowed: {', '.join(_ALLOWED_INTERVALS)}")

    if interval:
        pg_interval = _ALLOWED_INTERVALS[interval]
        bucket = func.time_bucket(text(f"'{pg_interval}'"), TelemetryRecord.time).label("bucket")
        stmt = (
            select(
                bucket,
                func.avg(TelemetryRecord.value_numeric).label("avg_value"),
            )
            .where(
                TelemetryRecord.sensor_id == sensor_id,
                TelemetryRecord.time >= start,
                TelemetryRecord.time <= end,
            )
            .group_by(text("bucket"))
            .order_by(text("bucket DESC"))
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        points = [
            TelemetryPointRead(
                time=row.bucket,
                sensor_id=sensor_id,
                value_numeric=float(row.avg_value) if row.avg_value is not None else None,
                value_text=None,
            )
            for row in reversed(rows)
        ]
    else:
        stmt = (
            select(TelemetryRecord)
            .where(
                TelemetryRecord.sensor_id == sensor_id,
                TelemetryRecord.time >= start,
                TelemetryRecord.time <= end,
            )
            .order_by(TelemetryRecord.time.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        points = [
            TelemetryPointRead(
                time=r.time,
                sensor_id=r.sensor_id,
                value_numeric=r.value_numeric,
                value_text=r.value_text,
            )
            for r in reversed(rows)
        ]

    return TelemetrySeriesRead(sensor_id=sensor_id, points=points, count=len(points))


@router.get("/{sensor_id}/latest", response_model=TelemetryLatest)
async def get_telemetry_latest(
    sensor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest telemetry reading for a sensor."""
    stmt = (
        select(Sensor)
        .where(Sensor.id == sensor_id)
    )
    sensor = (await db.execute(stmt)).scalar_one_or_none()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    latest_stmt = (
        select(TelemetryRecord)
        .where(TelemetryRecord.sensor_id == sensor_id)
        .order_by(desc(TelemetryRecord.time))
        .limit(1)
    )
    record = (await db.execute(latest_stmt)).scalar_one_or_none()

    return TelemetryLatest(
        sensor_id=sensor.id,
        sensor_key=sensor.key,
        sensor_name=sensor.name,
        value_numeric=record.value_numeric if record else None,
        value_text=record.value_text if record else None,
        time=record.time if record else None,
    )


@router.get("/{sensor_id}/summary", response_model=TelemetrySummary)
async def get_telemetry_summary(
    sensor_id: uuid.UUID,
    start: datetime | None = Query(default=None, description="Start of time range"),
    end: datetime | None = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
):
    """Get min/max/avg/count summary for a sensor over a time window."""
    sensor = await db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    if end is None:
        end = datetime.now(UTC)
    if start is None:
        start = end - timedelta(hours=1)

    stmt = (
        select(
            func.count().label("count"),
            func.min(TelemetryRecord.value_numeric).label("min"),
            func.max(TelemetryRecord.value_numeric).label("max"),
            func.avg(TelemetryRecord.value_numeric).label("avg"),
            func.min(TelemetryRecord.time).label("first_time"),
            func.max(TelemetryRecord.time).label("last_time"),
        )
        .where(
            TelemetryRecord.sensor_id == sensor_id,
            TelemetryRecord.time >= start,
            TelemetryRecord.time <= end,
        )
    )
    row = (await db.execute(stmt)).one()

    return TelemetrySummary(
        sensor_id=sensor_id,
        count=row.count,
        min=float(row.min) if row.min is not None else None,
        max=float(row.max) if row.max is not None else None,
        avg=float(row.avg) if row.avg is not None else None,
        first_time=row.first_time,
        last_time=row.last_time,
    )


@router.get("/device/{device_id}", response_model=DeviceTelemetryRead)
async def get_device_latest_telemetry(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest reading from every sensor on a device."""
    stmt = (
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.sensors))
    )
    device = (await db.execute(stmt)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    # Fetch latest telemetry for all sensors in one query using DISTINCT ON
    sensor_ids = [s.id for s in device.sensors]
    record_map: dict = {}
    if sensor_ids:
        latest_stmt = (
            select(TelemetryRecord)
            .where(TelemetryRecord.sensor_id.in_(sensor_ids))
            .distinct(TelemetryRecord.sensor_id)
            .order_by(TelemetryRecord.sensor_id, TelemetryRecord.time.desc())
        )
        latest_records = (await db.execute(latest_stmt)).scalars().all()
        record_map = {r.sensor_id: r for r in latest_records}

    readings: list[TelemetryLatest] = []
    for sensor in device.sensors:
        record = record_map.get(sensor.id)
        readings.append(
            TelemetryLatest(
                sensor_id=sensor.id,
                sensor_key=sensor.key,
                sensor_name=sensor.name,
                value_numeric=record.value_numeric if record else None,
                value_text=record.value_text if record else None,
                time=record.time if record else None,
            )
        )

    return DeviceTelemetryRead(
        device_id=device.id,
        device_name=device.name,
        readings=readings,
    )
