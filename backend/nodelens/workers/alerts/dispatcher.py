"""Persist alert history + publish dispatch events to integration plugins."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from nodelens.constants import ALERT_DISPATCH_STREAM
from nodelens.db.models import (
    AlertHistory,
    AlertRuleChannel,
    Device,
    NotificationChannel,
    Plugin,
    Sensor,
)
from nodelens.schemas.events import AlertMessage
from nodelens.sdk.integration_runtime import encode_dispatch_event

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

    from nodelens.workers.alerts.evaluator import FireDecision

logger = logging.getLogger("nodelens.alerts.dispatcher")


async def _resolve_device_name(session: AsyncSession, sensor_id: str) -> str:
    stmt = (
        select(Device.name)
        .join(Sensor, Sensor.device_id == Device.id)
        .where(Sensor.id == sensor_id)
    )
    name = (await session.execute(stmt)).scalar()
    return name or "<unknown>"


async def _load_active_channels(
    session: AsyncSession, rule_id: str
) -> list[tuple[NotificationChannel, Plugin]]:
    """Channels linked to the rule where both channel and plugin are active."""
    stmt = (
        select(NotificationChannel, Plugin)
        .join(AlertRuleChannel, AlertRuleChannel.channel_id == NotificationChannel.id)
        .join(Plugin, Plugin.id == NotificationChannel.plugin_id)
        .where(
            AlertRuleChannel.rule_id == rule_id,
            NotificationChannel.is_active.is_(True),
            Plugin.is_active.is_(True),
        )
    )
    return list((await session.execute(stmt)).all())


async def dispatch_fires(
    session: AsyncSession,
    r: aioredis.Redis,
    fires: list[FireDecision],
) -> None:
    """Write history rows and publish one dispatch event per active linked channel."""
    if not fires:
        return

    for fire in fires:
        device_name = await _resolve_device_name(session, fire.rule.sensor_id)
        history = AlertHistory(
            rule_id=fire.rule.id,
            triggered_value=fire.triggered_value,
            message=fire.message,
            triggered_at=fire.triggered_at,
        )
        session.add(history)

        channels = await _load_active_channels(session, fire.rule.id)
        if not channels:
            logger.warning(
                "Fired rule %s but no active channels are linked — history written, no delivery.",
                fire.rule.name,
            )
            continue

        alert_message = AlertMessage(
            rule_name=fire.rule.name,
            device_name=device_name,
            triggered_value=float(fire.triggered_value if fire.triggered_value is not None else 0.0),
            message=fire.message,
            triggered_at=fire.triggered_at,
        )

        for channel, plugin in channels:
            event_fields = encode_dispatch_event(
                plugin_id=str(plugin.id),
                channel_id=str(channel.id),
                channel_config=channel.config or {},
                message=alert_message,
            )
            await r.xadd(ALERT_DISPATCH_STREAM, event_fields)
            logger.info(
                "Dispatched rule=%s channel=%s plugin=%s",
                fire.rule.name,
                channel.name,
                plugin.module_name,
            )

    await session.commit()
