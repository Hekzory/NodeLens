"""Notification channel CRUD — destinations for alert dispatches."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.db.models import NotificationChannel, Plugin
from nodelens.schemas.notifications import (
    NotificationChannelCreate,
    NotificationChannelRead,
    NotificationChannelUpdate,
)

router = APIRouter(prefix="/api/alerts/channels", tags=["alerts", "channels"])


async def _to_read(session: AsyncSession, ch: NotificationChannel) -> NotificationChannelRead:
    """Build a response with the linked plugin's module_name attached for UI."""
    data = NotificationChannelRead.model_validate(ch)
    plugin = await session.get(Plugin, ch.plugin_id)
    data.plugin_module_name = plugin.module_name if plugin else None
    return data


@router.get("", response_model=list[NotificationChannelRead])
async def list_channels(
    plugin_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NotificationChannel).order_by(NotificationChannel.created_at.desc())
    if plugin_id is not None:
        stmt = stmt.where(NotificationChannel.plugin_id == plugin_id)
    if is_active is not None:
        stmt = stmt.where(NotificationChannel.is_active == is_active)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _to_read(db, c) for c in rows]


@router.post("", response_model=NotificationChannelRead, status_code=201)
async def create_channel(
    body: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
):
    plugin = await db.get(Plugin, body.plugin_id)
    if plugin is None:
        raise HTTPException(status_code=400, detail="Plugin not found")
    if plugin.plugin_type != "integration":
        raise HTTPException(
            status_code=400,
            detail="Channel plugin must be of type 'integration'",
        )

    channel = NotificationChannel(**body.model_dump())
    db.add(channel)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Channel with this name already exists") from exc
    await db.refresh(channel)
    return await _to_read(db, channel)


@router.get("/{channel_id}", response_model=NotificationChannelRead)
async def get_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ch = await db.get(NotificationChannel, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return await _to_read(db, ch)


@router.patch("/{channel_id}", response_model=NotificationChannelRead)
async def update_channel(
    channel_id: uuid.UUID,
    body: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db),
):
    ch = await db.get(NotificationChannel, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    update_data = body.model_dump(exclude_unset=True)

    if "plugin_id" in update_data:
        plugin = await db.get(Plugin, update_data["plugin_id"])
        if plugin is None:
            raise HTTPException(status_code=400, detail="Plugin not found")
        if plugin.plugin_type != "integration":
            raise HTTPException(
                status_code=400,
                detail="Channel plugin must be of type 'integration'",
            )

    for field, value in update_data.items():
        setattr(ch, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Channel with this name already exists") from exc
    await db.refresh(ch)
    return await _to_read(db, ch)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ch = await db.get(NotificationChannel, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(ch)
    await db.commit()
