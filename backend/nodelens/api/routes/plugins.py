"""Plugin endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens import plugin_config
from nodelens.api.deps import get_db
from nodelens.db.models import Device, Plugin
from nodelens.schemas.devices import DeviceRead
from nodelens.schemas.plugins import (
    PluginConfigFieldRead,
    PluginConfigRead,
    PluginConfigUpdate,
    PluginConfigUpdateResponse,
    PluginRead,
    PluginUpdate,
)
from nodelens.system_settings import runtime_settings

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

SECRET_MASK = "••••••"


def _to_field_read(
    field: plugin_config.PluginConfigField,
    value: Any,
    has_override: bool,
) -> PluginConfigFieldRead:
    """Serialize one config field, masking secrets in both value and default."""
    if field.value_type == "secret":
        out_value: Any = SECRET_MASK if has_override and value else None
        out_default: Any = None
    else:
        out_value = value
        out_default = field.default
    return PluginConfigFieldRead(
        key=field.key,
        label=field.label,
        group=field.group,
        value_type=field.value_type,
        value=out_value,
        default=out_default,
        is_default=not has_override,
        unit=field.unit,
        min=field.min,
        max=field.max,
        requires_restart=field.requires_restart,
        help=field.help,
    )


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

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A plugin with this module name already exists") from exc
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


@router.get("/{plugin_id}/config", response_model=PluginConfigRead)
async def get_plugin_config(
    plugin_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Schema + current effective values for one plugin (secrets masked)."""
    loaded = await plugin_config.load(db, plugin_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    plugin, schema, stored = loaded
    eff = plugin_config.effective_values(schema, stored)
    fields = [_to_field_read(f, eff[f.key], f.key in stored) for f in schema]
    return PluginConfigRead(
        plugin_id=plugin_id,
        config_version=plugin.config_version,
        fields=fields,
    )


@router.patch("/{plugin_id}/config", response_model=PluginConfigUpdateResponse)
async def update_plugin_config(
    plugin_id: uuid.UUID,
    body: PluginConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Validate + persist a batch of config overrides.

    Bumps ``config_version`` so the plugin worker supervisor restarts the
    affected subprocess on its next DB poll.
    """
    if not body.updates:
        raise HTTPException(status_code=422, detail="updates: must not be empty")
    try:
        await plugin_config.update(db, plugin_id, body.updates)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Plugin not found") from exc
    except plugin_config.PluginConfigValidationError as exc:
        detail: dict[str, Any] = {}
        if exc.field_errors:
            detail["field_errors"] = exc.field_errors
        if exc.general:
            detail["error"] = exc.general
        raise HTTPException(status_code=422, detail=detail) from None

    await db.commit()

    loaded = await plugin_config.load(db, plugin_id)
    if loaded is None:  # extreme race — row deleted mid-PATCH
        raise HTTPException(status_code=404, detail="Plugin not found")
    plugin, schema, stored = loaded
    eff = plugin_config.effective_values(schema, stored)
    fields = [_to_field_read(f, eff[f.key], f.key in stored) for f in schema]
    cfg = PluginConfigRead(
        plugin_id=plugin_id,
        config_version=plugin.config_version,
        fields=fields,
    )
    return PluginConfigUpdateResponse(
        config=cfg,
        requires_restart_keys=[f.key for f in schema if f.requires_restart],
    )


@router.delete("/{plugin_id}/config", status_code=204)
async def reset_plugin_config(
    plugin_id: uuid.UUID,
    key: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Reset overrides — all keys (no query) or a single ``?key=foo``."""
    try:
        await plugin_config.reset(db, plugin_id, [key] if key else None)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Plugin not found") from exc
    await db.commit()


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
    online_minutes = await runtime_settings.get_int("online_threshold_minutes")
    cutoff = datetime.now(UTC) - timedelta(minutes=online_minutes)
    results = []
    for device in devices:
        data = DeviceRead.model_validate(device)
        data.sensor_count = len(device.sensors)
        data.is_online = (
            plugin.is_active
            and device.last_seen is not None
            and device.last_seen >= cutoff
        )
        results.append(data)
    return results
