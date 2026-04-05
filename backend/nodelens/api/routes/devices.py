"""Device & sensor endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens.api.deps import get_db
from nodelens.db.models import Device, Sensor
from nodelens.schemas.devices import DeviceDetail, DeviceRead, SensorBrief, SensorRead

router = APIRouter(prefix="/api/devices", tags=["devices"])

ONLINE_THRESHOLD = timedelta(minutes=30)


def _compute_online(device: Device) -> bool:
    """A device is online only if its plugin is active and it was seen recently."""
    if not device.plugin.is_active:
        return False
    if device.last_seen is None:
        return False
    cutoff = datetime.now(UTC) - ONLINE_THRESHOLD
    return device.last_seen >= cutoff


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    plugin_id: uuid.UUID | None = Query(default=None, description="Filter by plugin"),
    is_online: bool | None = Query(default=None, description="Filter by online status"),
    db: AsyncSession = Depends(get_db),
):
    """List all devices with optional filters."""
    stmt = (
        select(Device)
        .options(selectinload(Device.sensors), selectinload(Device.plugin))
        .order_by(Device.created_at)
    )
    if plugin_id is not None:
        stmt = stmt.where(Device.plugin_id == plugin_id)

    devices = (await db.execute(stmt)).scalars().all()
    results = []
    for device in devices:
        online = _compute_online(device)
        if is_online is not None and online != is_online:
            continue
        data = DeviceRead.model_validate(device)
        data.is_online = online
        data.sensor_count = len(device.sensors)
        results.append(data)
    return results


@router.get("/{device_id}", response_model=DeviceDetail)
async def get_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get device detail with nested sensors."""
    stmt = (
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.sensors), selectinload(Device.plugin))
    )
    device = (await db.execute(stmt)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceDetail(
        id=device.id,
        plugin_id=device.plugin_id,
        external_id=device.external_id,
        name=device.name,
        location=device.location,
        is_online=_compute_online(device),
        last_seen=device.last_seen,
        created_at=device.created_at,
        sensors=[SensorBrief.model_validate(s) for s in device.sensors],
    )


@router.get("/{device_id}/sensors", response_model=list[SensorRead])
async def list_device_sensors(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List sensors belonging to a device."""
    # Verify device exists
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    stmt = (
        select(Sensor)
        .where(Sensor.device_id == device_id)
        .order_by(Sensor.key)
    )
    sensors = (await db.execute(stmt)).scalars().all()
    return [SensorRead.model_validate(s) for s in sensors]
