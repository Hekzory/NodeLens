"""Reads telemetry events from the Redis stream and writes them to TimescaleDB."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from nodelens.constants import (
    INGEST_CONSUMER_GROUP,
    INGEST_CONSUMER_NAME,
    TELEMETRY_STREAM,
)
from nodelens.redis.client import get_redis
from nodelens.redis.streams import ack, ensure_consumer_group, read_stream
from nodelens.schemas.events import TelemetryEvent
from nodelens.workers.ingestor.writer import write_batch

logger = logging.getLogger("nodelens.ingestor.consumer")

_HEARTBEAT = Path("/tmp/.healthcheck")


def _parse_event(fields: dict) -> TelemetryEvent:
    return TelemetryEvent(
        device_id=fields["device_id"],
        sensor_id=fields["sensor_id"],
        value=float(fields["value"]),
        timestamp=datetime.fromisoformat(fields["timestamp"]),
    )


async def run_consumer() -> None:
    r = await get_redis()
    await ensure_consumer_group(r, TELEMETRY_STREAM, INGEST_CONSUMER_GROUP)
    logger.info(
        "Consumer loop started  stream=%s  group=%s",
        TELEMETRY_STREAM,
        INGEST_CONSUMER_GROUP,
    )

    while True:
        try:
            messages = await read_stream(
                r,
                group=INGEST_CONSUMER_GROUP,
                consumer=INGEST_CONSUMER_NAME,
                stream=TELEMETRY_STREAM,
                count=50,
                block=2000,
            )
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            logger.error("Redis connection error: %s. Retrying in 5s…", exc)
            await asyncio.sleep(5)
            continue

        _HEARTBEAT.touch()

        if not messages:
            continue

        events: list[TelemetryEvent] = []
        good_ids: list[str] = []
        bad_ids: list[str] = []

        for msg_id, fields in messages:
            try:
                events.append(_parse_event(fields))
                good_ids.append(msg_id)
            except (KeyError, ValueError) as exc:
                logger.warning("Dropping malformed message %s: %s", msg_id, exc)
                bad_ids.append(msg_id)

        # ACK unparseable messages so they don't block the group
        if bad_ids:
            await ack(r, TELEMETRY_STREAM, INGEST_CONSUMER_GROUP, *bad_ids)

        if not events:
            continue

        try:
            written = await write_batch(events)
            await ack(r, TELEMETRY_STREAM, INGEST_CONSUMER_GROUP, *good_ids)
            logger.info("Ingested batch: %d written / %d received.", written, len(events))
        except Exception:
            # Don't ACK — messages will be redelivered on next XREADGROUP
            logger.exception("Batch write failed (%d events). Will retry.", len(events))
