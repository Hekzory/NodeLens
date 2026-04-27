"""Periodic scanner for `condition=no_data` alert rules.

Fires when a sensor has been silent for at least `duration_seconds`. Runs
alongside the event-driven engine inside the alerts worker. Four guards must
pass before a fire is emitted; see _scan_once() for details.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from nodelens.config import settings
from nodelens.db.models import AlertRule, TelemetryRecord
from nodelens.db.session import async_session
from nodelens.heartbeat import touch_heartbeat
from nodelens.redis.client import get_redis
from nodelens.workers.alerts.dispatcher import dispatch_fires
from nodelens.workers.alerts.evaluator import FireDecision, is_in_cooldown
from nodelens.workers.alerts.liveness import (
    mark_scanner_started,
    scanner_uptime,
    time_since_last_event,
)

if TYPE_CHECKING:
    import uuid

    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nodelens.alerts.no_data_scanner")


async def _load_active_no_data_rules(session: AsyncSession) -> list[AlertRule]:
    stmt = select(AlertRule).where(
        AlertRule.condition == "no_data",
        AlertRule.is_active.is_(True),
    )
    return list((await session.execute(stmt)).scalars().all())


async def _last_seen_for_sensors(
    session: AsyncSession, sensor_ids: set[uuid.UUID]
) -> dict[uuid.UUID, datetime | None]:
    """One grouped MAX(time) query for the given sensor set. Missing sensors → None."""
    out: dict[uuid.UUID, datetime | None] = dict.fromkeys(sensor_ids)
    if not sensor_ids:
        return out
    stmt = (
        select(TelemetryRecord.sensor_id, func.max(TelemetryRecord.time))
        .where(TelemetryRecord.sensor_id.in_(sensor_ids))
        .group_by(TelemetryRecord.sensor_id)
    )
    rows = (await session.execute(stmt)).all()
    out.update(dict(rows))
    return out


async def _scan_once(session: AsyncSession, r: aioredis.Redis, now: datetime) -> None:
    rules = await _load_active_no_data_rules(session)
    if not rules:
        return

    sensor_ids = {rule.sensor_id for rule in rules}
    last_seen_by_sensor = await _last_seen_for_sensors(session, sensor_ids)

    decisions: list[FireDecision] = []
    for rule in rules:
        # Defensive: API rejects this on create, but trust nothing in the scanner.
        if rule.duration_seconds <= 0:
            continue

        threshold = timedelta(seconds=rule.duration_seconds)

        # Guard 1: sensor never reported any telemetry — treat as not-yet-deployed.
        last_seen = last_seen_by_sensor.get(rule.sensor_id)
        if last_seen is None:
            continue

        # Guard 2: sensor produced data within the window.
        elapsed = now - last_seen
        if elapsed < threshold:
            continue

        # Guard 3: scanner-uptime grace. After a container restart we cannot
        # distinguish "always silent" from "we were down" — defer until we've
        # been observing the system for at least the rule's window.
        uptime = scanner_uptime(now)
        if uptime is None or uptime < threshold:
            continue

        # Guard 4: pipeline-liveness. If no telemetry events have flowed
        # through the engine recently, the silence is system-wide, not
        # sensor-specific. Suppressing here trades a missed fire for the
        # avoidance of mass false positives.
        since_event = time_since_last_event(now)
        if since_event is None or since_event >= threshold:
            continue

        # Guard 5: existing cooldown enforcement.
        if await is_in_cooldown(session, rule, now):
            continue

        elapsed_seconds = int(elapsed.total_seconds())
        msg = (
            f"{rule.name}: no data for {elapsed_seconds}s "
            f"(threshold {rule.duration_seconds}s, last seen {last_seen.isoformat()})"
        )
        decisions.append(
            FireDecision(
                rule=rule,
                triggered_value=float(elapsed_seconds),
                message=msg,
                triggered_at=now,
            )
        )

    if decisions:
        await dispatch_fires(session, r, decisions)


async def run_no_data_scanner() -> None:
    interval = max(1, int(settings.NO_DATA_SCAN_INTERVAL_SECONDS))
    mark_scanner_started(datetime.now(UTC))
    logger.info(
        "no_data scanner started  interval=%ss", interval,
    )

    while True:
        try:
            r = await get_redis()
            async with async_session() as session:
                await _scan_once(session, r, datetime.now(UTC))
            touch_heartbeat()
        except Exception:
            logger.exception("no_data scan tick failed; will retry on next interval")
        await asyncio.sleep(interval)
