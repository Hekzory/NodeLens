"""Plugin runtime context — provides Redis publish and registration helpers."""

from __future__ import annotations

import dataclasses

import redis.asyncio as aioredis

from nodelens.constants import REGISTRATION_STREAM, TELEMETRY_STREAM
from nodelens.redis.streams import publish_event
from nodelens.schemas.events import (
    RegisterDeviceEvent,
    RegisterPluginEvent,
    RegisterSensorEvent,
    TelemetryEvent,
)


class PluginContext:
    """Runtime context injected into every plugin by the plugin runner.

    Provides methods to:
    * register the plugin, its devices, and sensors (via the registration stream);
    * publish normalised telemetry events (via the telemetry stream).
    """

    def __init__(
        self,
        *,
        redis_url: str,
        plugin_id: str,
        plugin_type: str,
        module_name: str,
        display_name: str,
        version: str,
    ) -> None:
        self._redis_url = redis_url
        self._plugin_id = plugin_id
        self._plugin_type = plugin_type
        self._module_name = module_name
        self._display_name = display_name
        self._version = version
        self._redis: aioredis.Redis | None = None

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    # ── Lifecycle ───────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the shared Redis connection."""
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def _r(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("PluginContext not connected — call connect() first.")
        return self._redis

    # ── Registration helpers ────────────────────────────────────

    async def register_plugin(self) -> None:
        """Publish a register_plugin event to the registration stream."""
        event = RegisterPluginEvent(
            plugin_id=self._plugin_id,
            plugin_type=self._plugin_type,
            module_name=self._module_name,
            display_name=self._display_name,
            version=self._version,
        )
        fields = dataclasses.asdict(event)
        fields["event_type"] = "register_plugin"
        await self._r().xadd(REGISTRATION_STREAM, fields)

    async def register_device(
        self,
        *,
        device_id: str,
        external_id: str,
        name: str,
        location: str = "",
    ) -> None:
        """Publish a register_device event to the registration stream."""
        event = RegisterDeviceEvent(
            device_id=device_id,
            plugin_id=self._plugin_id,
            external_id=external_id,
            name=name,
            location=location,
        )
        fields = dataclasses.asdict(event)
        fields["event_type"] = "register_device"
        await self._r().xadd(REGISTRATION_STREAM, fields)

    async def register_sensor(
        self,
        *,
        sensor_id: str,
        device_id: str,
        key: str,
        name: str,
        unit: str = "",
        value_type: str = "numeric",
    ) -> None:
        """Publish a register_sensor event to the registration stream."""
        event = RegisterSensorEvent(
            sensor_id=sensor_id,
            device_id=device_id,
            key=key,
            name=name,
            unit=unit,
            value_type=value_type,
        )
        fields = dataclasses.asdict(event)
        fields["event_type"] = "register_sensor"
        await self._r().xadd(REGISTRATION_STREAM, fields)

    # ── Telemetry publishing ────────────────────────────────────

    async def publish_telemetry(self, event: TelemetryEvent) -> None:
        """Publish a normalised telemetry event to the telemetry stream."""
        await publish_event(self._r(), TELEMETRY_STREAM, event)
