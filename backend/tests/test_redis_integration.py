"""Integration test against real Redis Streams (testcontainers)."""

from datetime import UTC, datetime

import pytest

from nodelens.redis.streams import ack, ensure_consumer_group, publish_event, read_stream
from nodelens.schemas.events import TelemetryEvent

pytestmark = pytest.mark.integration

STREAM = "telemetry_events"
GROUP = "ingestor"


async def test_publish_read_ack_round_trip(redis_conn):
    """A published event is delivered to the consumer group, then ack'd off it."""
    await ensure_consumer_group(redis_conn, STREAM, GROUP)
    ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    msg_id = await publish_event(
        redis_conn,
        STREAM,
        TelemetryEvent(device_id="dev-1", sensor_id="sen-1", value=42.0, timestamp=ts),
    )
    assert msg_id

    messages = await read_stream(redis_conn, GROUP, "c1", STREAM, block=500)
    assert len(messages) == 1
    read_id, fields = messages[0]
    assert read_id == msg_id
    assert fields["device_id"] == "dev-1"
    assert fields["value"] == "42.0"
    assert fields["timestamp"] == ts.isoformat()

    await ack(redis_conn, STREAM, GROUP, read_id)
    assert await read_stream(redis_conn, GROUP, "c1", STREAM, block=200) == []
