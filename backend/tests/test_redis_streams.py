"""Tests for nodelens.redis.streams — XADD/XREADGROUP/XACK helpers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as aioredis

from nodelens.redis.streams import (
    ack,
    ensure_consumer_group,
    publish_event,
    read_stream,
)
from nodelens.schemas.events import TelemetryEvent
from tests.conftest import DEVICE_ID_STR, SENSOR_ID_STR

_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _event(value: float = 23.5) -> TelemetryEvent:
    return TelemetryEvent(
        device_id=DEVICE_ID_STR,
        sensor_id=SENSOR_ID_STR,
        value=value,
        timestamp=_TS,
    )


@pytest.fixture
def redis_mock():
    return AsyncMock()


class TestPublishEvent:
    async def test_xadd_called_with_serialised_fields(self, redis_mock):
        redis_mock.xadd.return_value = "1700000000000-0"
        msg_id = await publish_event(redis_mock, "telemetry_events", _event())

        assert msg_id == "1700000000000-0"
        redis_mock.xadd.assert_awaited_once()
        args, _ = redis_mock.xadd.call_args
        stream, fields = args
        assert stream == "telemetry_events"
        assert fields == {
            "device_id": DEVICE_ID_STR,
            "sensor_id": SENSOR_ID_STR,
            "value": "23.5",
            "timestamp": _TS.isoformat(),
        }

    async def test_value_is_stringified(self, redis_mock):
        redis_mock.xadd.return_value = "x"
        await publish_event(redis_mock, "s", _event(value=0.0))
        fields = redis_mock.xadd.call_args.args[1]
        assert isinstance(fields["value"], str)
        assert fields["value"] == "0.0"


class TestEnsureConsumerGroup:
    async def test_creates_group_with_mkstream(self, redis_mock):
        await ensure_consumer_group(redis_mock, "telemetry_events", "ingestor")

        redis_mock.xgroup_create.assert_awaited_once_with(
            "telemetry_events", "ingestor", id="0", mkstream=True
        )

    async def test_swallows_busygroup_error(self, redis_mock):
        redis_mock.xgroup_create.side_effect = aioredis.ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )
        # Must not raise — group already exists is the no-op path.
        await ensure_consumer_group(redis_mock, "stream", "group")

    async def test_reraises_other_response_errors(self, redis_mock):
        redis_mock.xgroup_create.side_effect = aioredis.ResponseError("WRONGTYPE not a stream")
        with pytest.raises(aioredis.ResponseError, match="WRONGTYPE"):
            await ensure_consumer_group(redis_mock, "stream", "group")


class TestReadStream:
    async def test_returns_empty_list_when_no_results(self, redis_mock):
        redis_mock.xreadgroup.return_value = []
        msgs = await read_stream(redis_mock, "g", "c", "s")
        assert msgs == []

    async def test_returns_empty_list_when_none(self, redis_mock):
        redis_mock.xreadgroup.return_value = None
        msgs = await read_stream(redis_mock, "g", "c", "s")
        assert msgs == []

    async def test_flattens_messages_across_streams(self, redis_mock):
        redis_mock.xreadgroup.return_value = [
            (
                "telemetry_events",
                [
                    ("1-0", {"device_id": "d1"}),
                    ("1-1", {"device_id": "d2"}),
                ],
            ),
        ]
        msgs = await read_stream(redis_mock, "g", "c", "telemetry_events")
        assert msgs == [
            ("1-0", {"device_id": "d1"}),
            ("1-1", {"device_id": "d2"}),
        ]

    async def test_passes_through_xreadgroup_arguments(self, redis_mock):
        redis_mock.xreadgroup.return_value = []
        await read_stream(redis_mock, "g1", "c1", "s1", count=5, block=100)

        redis_mock.xreadgroup.assert_awaited_once_with(
            groupname="g1",
            consumername="c1",
            streams={"s1": ">"},
            count=5,
            block=100,
        )

    async def test_default_count_and_block(self, redis_mock):
        redis_mock.xreadgroup.return_value = []
        await read_stream(redis_mock, "g", "c", "s")
        kwargs = redis_mock.xreadgroup.call_args.kwargs
        assert kwargs["count"] == 100
        assert kwargs["block"] == 2000


class TestAck:
    async def test_no_call_when_no_ids(self, redis_mock):
        await ack(redis_mock, "stream", "group")
        redis_mock.xack.assert_not_called()

    async def test_forwards_single_id(self, redis_mock):
        await ack(redis_mock, "stream", "group", "1-0")
        redis_mock.xack.assert_awaited_once_with("stream", "group", "1-0")

    async def test_forwards_multiple_ids(self, redis_mock):
        await ack(redis_mock, "stream", "group", "1-0", "1-1", "1-2")
        redis_mock.xack.assert_awaited_once_with("stream", "group", "1-0", "1-1", "1-2")
