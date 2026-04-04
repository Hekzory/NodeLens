"""Plugin endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens.api.deps import get_db
from nodelens.db.models import Device, Plugin
from nodelens.schemas.devices import DeviceRead
from nodelens.schemas.plugins import PluginRead, PluginUpdate

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("", response_model=list[PluginRead])
async def list_plugins(db: AsyncSession = Depends(get_db)):
    """List all registered plugins with device counts."""
    stmt = (
        select(
            Plugin,
            func.count(Device.id).label("device_count"),
        )
        .outerjoin(Device, Device.plugin_id == Plugin.id)
        .group_by(Plugin.id)
        .order_by(Plugin.created_at)
    )
    rows = (await db.execute(stmt)).all()
    results = []
    for plugin, device_count in rows:
        data = PluginRead.model_validate(plugin)
        data.device_count = device_count
        results.append(data)
    return results


@router.get("/{plugin_id}", response_model=PluginRead)
async def get_plugin(plugin_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single plugin by ID."""
    stmt = (
        select(
            Plugin,
            func.count(Device.id).label("device_count"),
        )
        .outerjoin(Device, Device.plugin_id == Plugin.id)
        .where(Plugin.id == plugin_id)
        .group_by(Plugin.id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    plugin, device_count = row
    data = PluginRead.model_validate(plugin)
    data.device_count = device_count
    return data


@router.patch("/{plugin_id}", response_model=PluginRead)
async def update_plugin(
    plugin_id: uuid.UUID,
    body: PluginUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update plugin fields (e.g. toggle is_active)."""
    plugin = await db.get(Plugin, plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plugin, field, value)

    await db.commit()
    await db.refresh(plugin)

    # Re-query with device count
    stmt = (
        select(func.count(Device.id))
        .where(Device.plugin_id == plugin_id)
    )
    device_count = (await db.execute(stmt)).scalar() or 0
    data = PluginRead.model_validate(plugin)
    data.device_count = device_count
    return data


@router.get("/{plugin_id}/devices", response_model=list[DeviceRead])
async def list_plugin_devices(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List devices belonging to a specific plugin."""
    # Verify plugin exists
    plugin = await db.get(Plugin, plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Query devices then count sensors
    devices_stmt = (
        select(Device)
        .where(Device.plugin_id == plugin_id)
        .options(selectinload(Device.sensors))
        .order_by(Device.created_at)
    )
    devices = (await db.execute(devices_stmt)).scalars().all()
    results = []
    for device in devices:
        data = DeviceRead.model_validate(device)
        data.sensor_count = len(device.sensors)
        results.append(data)
    return results
