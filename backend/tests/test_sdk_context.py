"""Tests for nodelens.sdk.context.PluginContext."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nodelens.constants import REGISTRATION_STREAM, TELEMETRY_STREAM
from nodelens.schemas.events import TelemetryEvent
from nodelens.sdk.context import PluginContext
from tests.conftest import DEVICE_ID_STR, PLUGIN_ID_STR, SENSOR_ID_STR


def _make_ctx(**overrides) -> PluginContext:
    defaults = {
        "redis_url": "redis://localhost:6379/0",
        "plugin_id": PLUGIN_ID_STR,
        "plugin_type": "device",
        "module_name": "demo_sender",
        "display_name": "Demo Sender",
        "version": "1.2.3",
        "description": "demo plugin",
    }
    defaults.update(overrides)
    return PluginContext(**defaults)


class TestPluginIdProperty:
    def test_returns_constructor_value(self):
        ctx = _make_ctx(plugin_id="abc-123")
        assert ctx.plugin_id == "abc-123"


class TestConnectClose:
    async def test_connect_opens_redis(self):
        ctx = _make_ctx()
        fake_redis = MagicMock()
        with patch(
            "nodelens.sdk.context.aioredis.from_url", return_value=fake_redis
        ) as from_url:
            await ctx.connect()

        from_url.assert_called_once()
        args, kwargs = from_url.call_args
        assert args[0] == "redis://localhost:6379/0"
        assert kwargs.get("decode_responses") is True
        assert ctx._redis is fake_redis

    async def test_close_when_never_connected_is_noop(self):
        ctx = _make_ctx()
        # Should not raise.
        await ctx.close()
        assert ctx._redis is None

    async def test_close_aclose_and_clears(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.aclose = AsyncMock()
        ctx._redis = fake

        await ctx.close()

        fake.aclose.assert_awaited_once()
        assert ctx._redis is None

    def test_r_raises_when_not_connected(self):
        ctx = _make_ctx()
        with pytest.raises(RuntimeError, match="not connected"):
            ctx._r()

    def test_r_returns_underlying_client(self):
        ctx = _make_ctx()
        fake = MagicMock()
        ctx._redis = fake
        assert ctx._r() is fake


class TestRegisterPlugin:
    async def test_xadds_event_to_registration_stream(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock()
        ctx._redis = fake

        await ctx.register_plugin()

        fake.xadd.assert_awaited_once()
        stream, fields = fake.xadd.call_args.args
        assert stream == REGISTRATION_STREAM
        assert fields == {
            "event_type": "register_plugin",
            "plugin_id": PLUGIN_ID_STR,
            "plugin_type": "device",
            "module_name": "demo_sender",
            "display_name": "Demo Sender",
            "version": "1.2.3",
            "description": "demo plugin",
        }

    async def test_raises_when_not_connected(self):
        ctx = _make_ctx()
        with pytest.raises(RuntimeError):
            await ctx.register_plugin()


class TestRegisterDevice:
    async def test_xadds_with_defaults(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock()
        ctx._redis = fake

        await ctx.register_device(
            device_id=DEVICE_ID_STR,
            external_id="ext-1",
            name="Living Room",
        )

        stream, fields = fake.xadd.call_args.args
        assert stream == REGISTRATION_STREAM
        assert fields["event_type"] == "register_device"
        assert fields["device_id"] == DEVICE_ID_STR
        assert fields["plugin_id"] == PLUGIN_ID_STR  # injected from ctx
        assert fields["external_id"] == "ext-1"
        assert fields["name"] == "Living Room"
        assert fields["location"] == ""

    async def test_xadds_with_explicit_location(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock()
        ctx._redis = fake

        await ctx.register_device(
            device_id=DEVICE_ID_STR,
            external_id="ext-1",
            name="LR",
            location="Floor 2",
        )
        _, fields = fake.xadd.call_args.args
        assert fields["location"] == "Floor 2"


class TestRegisterSensor:
    async def test_xadds_with_defaults(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock()
        ctx._redis = fake

        await ctx.register_sensor(
            sensor_id=SENSOR_ID_STR,
            device_id=DEVICE_ID_STR,
            key="temp",
            name="Temperature",
        )

        stream, fields = fake.xadd.call_args.args
        assert stream == REGISTRATION_STREAM
        assert fields["event_type"] == "register_sensor"
        assert fields["sensor_id"] == SENSOR_ID_STR
        assert fields["device_id"] == DEVICE_ID_STR
        assert fields["key"] == "temp"
        assert fields["name"] == "Temperature"
        assert fields["unit"] == ""
        assert fields["value_type"] == "numeric"

    async def test_xadds_with_overrides(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock()
        ctx._redis = fake

        await ctx.register_sensor(
            sensor_id=SENSOR_ID_STR,
            device_id=DEVICE_ID_STR,
            key="hum",
            name="Humidity",
            unit="%",
            value_type="text",
        )
        _, fields = fake.xadd.call_args.args
        assert fields["unit"] == "%"
        assert fields["value_type"] == "text"


class TestPublishTelemetry:
    async def test_delegates_to_publish_event(self):
        ctx = _make_ctx()
        fake = MagicMock()
        fake.xadd = AsyncMock(return_value="1-0")
        ctx._redis = fake

        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        event = TelemetryEvent(
            device_id=DEVICE_ID_STR,
            sensor_id=SENSOR_ID_STR,
            value=42.0,
            timestamp=ts,
        )
        await ctx.publish_telemetry(event)

        fake.xadd.assert_awaited_once()
        stream, fields = fake.xadd.call_args.args
        assert stream == TELEMETRY_STREAM
        assert fields == {
            "device_id": DEVICE_ID_STR,
            "sensor_id": SENSOR_ID_STR,
            "value": "42.0",
            "timestamp": ts.isoformat(),
        }
