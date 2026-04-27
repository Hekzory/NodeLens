"""Alert worker main loop — telemetry stream → evaluate → dispatch."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from nodelens.constants import (
    ALERT_CONSUMER_GROUP,
    ALERT_CONSUMER_NAME,
    ALERT_DISPATCH_STREAM,
    TELEMETRY_STREAM,
)
from nodelens.db.session import async_session
from nodelens.heartbeat import touch_heartbeat
from nodelens.redis.client import get_redis
from nodelens.redis.parse import parse_telemetry_event
from nodelens.redis.streams import ack, ensure_consumer_group, read_stream
from nodelens.workers.alerts.dispatcher import dispatch_fires
from nodelens.workers.alerts.evaluator import (
    evaluate,
    load_active_rules_for_sensor,
)
from nodelens.workers.alerts.liveness import mark_event_processed

if TYPE_CHECKING:
    from nodelens.schemas.events import TelemetryEvent
    from nodelens.workers.alerts.evaluator import FireDecision

logger = logging.getLogger("nodelens.alerts.engine")


async def _process_event(event: TelemetryEvent) -> None:
    """Evaluate every active rule attached to this event's sensor."""
    async with async_session() as session:
        rules = await load_active_rules_for_sensor(session, event.sensor_id)
        if not rules:
            return

        decisions: list[FireDecision] = []
        for rule in rules:
            decision = await evaluate(session, rule, event)
            if decision is not None:
                decisions.append(decision)

        if decisions:
            r = await get_redis()
            await dispatch_fires(session, r, decisions)


async def run_engine() -> None:
    r = await get_redis()
    await ensure_consumer_group(r, TELEMETRY_STREAM, ALERT_CONSUMER_GROUP)
    # Pre-create the dispatch stream so integration plugins can subscribe early.
    await ensure_consumer_group(r, ALERT_DISPATCH_STREAM, "_bootstrap")
    logger.info(
        "Alert engine started  stream=%s  group=%s",
        TELEMETRY_STREAM,
        ALERT_CONSUMER_GROUP,
    )

    while True:
        try:
            messages = await read_stream(
                r,
                group=ALERT_CONSUMER_GROUP,
                consumer=ALERT_CONSUMER_NAME,
                stream=TELEMETRY_STREAM,
                count=50,
                block=2000,
            )
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            logger.error("Redis connection error: %s. Retrying in 5s…", exc)
            await asyncio.sleep(5)
            continue

        touch_heartbeat()

        if not messages:
            continue

        good_ids: list[str] = []
        bad_ids: list[str] = []
        events: list[TelemetryEvent] = []
        for msg_id, fields in messages:
            try:
                events.append(parse_telemetry_event(fields))
                good_ids.append(msg_id)
            except (KeyError, ValueError) as exc:
                logger.warning("Dropping malformed message %s: %s", msg_id, exc)
                bad_ids.append(msg_id)

        if bad_ids:
            await ack(r, TELEMETRY_STREAM, ALERT_CONSUMER_GROUP, *bad_ids)

        if events:
            # Pipeline-liveness signal for the no_data scanner.
            mark_event_processed(datetime.now(UTC))

        for event in events:
            try:
                await _process_event(event)
            except Exception:
                # Don't let one bad event kill the whole batch — log and move on.
                logger.exception("Failed to process event for sensor %s", event.sensor_id)

        if good_ids:
            await ack(r, TELEMETRY_STREAM, ALERT_CONSUMER_GROUP, *good_ids)
