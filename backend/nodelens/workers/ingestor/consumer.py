"""Reads telemetry events from the Redis stream and writes them to TimescaleDB."""

from __future__ import annotations

import asyncio
import logging

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from nodelens.constants import (
    INGEST_CONSUMER_GROUP,
    INGEST_CONSUMER_NAME,
    TELEMETRY_STREAM,
)
from nodelens.heartbeat import touch_heartbeat
from nodelens.redis.client import get_redis
from nodelens.redis.parse import partition_telemetry_batch
from nodelens.redis.streams import ack, ensure_consumer_group, read_stream
from nodelens.workers.ingestor.writer import write_batch

logger = logging.getLogger("nodelens.ingestor.consumer")


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

        touch_heartbeat()

        if not messages:
            continue

        events, good_ids, bad_ids = partition_telemetry_batch(messages, logger=logger)

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
