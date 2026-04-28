"""System settings: GET / PATCH / DELETE for runtime-configurable tunables.

Reads come from `runtime_settings` (TTL cache over `system_settings` table).
Writes go through `runtime_settings.update` which validates against the
registry and invalidates the cache.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.db.models import SystemSetting
from nodelens.schemas.system_settings import (
    SystemSettingRead,
    SystemSettingsUpdate,
    SystemSettingsUpdateResponse,
)
from nodelens.system_settings import REGISTRY, iter_settings, runtime_settings
from nodelens.system_settings.service import SettingsValidationError

router = APIRouter(prefix="/api/system/settings", tags=["system", "settings"])


async def _row_map(db: AsyncSession) -> dict[str, SystemSetting]:
    rows = (await db.execute(select(SystemSetting))).scalars().all()
    return {row.key: row for row in rows}


def _to_read(spec, value: Any, row: SystemSetting | None) -> SystemSettingRead:
    return SystemSettingRead(
        key=spec.key,
        label=spec.label,
        group=spec.group,
        value_type=spec.value_type,
        value=value,
        default=spec.default,
        is_default=row is None,
        unit=spec.unit,
        min=spec.min,
        max=spec.max,
        requires_restart=spec.requires_restart,
        affects_services=list(spec.affects_services),
        help=spec.help,
        updated_at=row.updated_at if row else None,
    )


@router.get("", response_model=list[SystemSettingRead])
async def list_settings(db: AsyncSession = Depends(get_db)):
    """All registered settings with current effective values + metadata."""
    rows = await _row_map(db)
    values = await runtime_settings.get_all()
    out: list[SystemSettingRead] = []
    for spec in iter_settings():
        out.append(_to_read(spec, values[spec.key], rows.get(spec.key)))
    return out


@router.get("/{key}", response_model=SystemSettingRead)
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    spec = REGISTRY.get(key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")
    rows = await _row_map(db)
    values = await runtime_settings.get_all()
    return _to_read(spec, values[key], rows.get(key))


@router.patch("", response_model=SystemSettingsUpdateResponse)
async def update_settings(
    body: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Validate + persist a batch of overrides; return canonicalized result."""
    if not body.updates:
        raise HTTPException(status_code=422, detail="updates: must not be empty")

    try:
        coerced = await runtime_settings.update(body.updates, session=db)
    except SettingsValidationError as exc:
        detail: dict[str, Any] = {}
        if exc.field_errors:
            detail["field_errors"] = exc.field_errors
        if exc.general:
            detail["error"] = exc.general
        raise HTTPException(status_code=422, detail=detail) from None

    await db.commit()

    # Build the response from the coerced values + the just-committed row map,
    # without going back through the (now-invalidated) runtime_settings cache —
    # that would issue a fresh DB read using a different session.
    rows = await _row_map(db)
    updated = [
        _to_read(REGISTRY[k], coerced[k], rows.get(k))
        for k in coerced
    ]
    requires_restart_keys = [k for k in coerced if REGISTRY[k].requires_restart]
    return SystemSettingsUpdateResponse(
        updated=updated, requires_restart_keys=requires_restart_keys
    )


@router.delete("/{key}", status_code=204)
async def reset_setting(key: str, db: AsyncSession = Depends(get_db)):
    """Drop the DB row so the value reverts to the registry default."""
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")
    try:
        await runtime_settings.reset([key], session=db)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await db.commit()
