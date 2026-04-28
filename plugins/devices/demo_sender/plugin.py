"""
Demo device plugin — generates synthetic telemetry data.

Replaces the old ``fake_publisher`` that was embedded in the ingestor.
Registers its own plugin record, devices, and sensors via the
registration stream, then publishes random values at per-sensor cadences.

Per-sensor value ranges and emit intervals are configurable via the
plugin-config UI; the constants below are the defaults the schema falls
back to when the operator hasn't overridden them.
"""

import asyncio
import logging
import random
from datetime import UTC, datetime
from typing import Any

from nodelens.sdk import DevicePlugin, TelemetryEvent

logger = logging.getLogger("nodelens.plugin.demo_sender")

# ── Deterministic UUIDs (must not collide with other plugins) ──

DEVICE_1 = "20000000-0000-0000-0000-000000000001"
DEVICE_2 = "20000000-0000-0000-0000-000000000002"
DEVICE_3 = "20000000-0000-0000-0000-000000000003"

SENSOR_TEMP_1 = "30000000-0000-0000-0000-000000000001"
SENSOR_HUM_1 = "30000000-0000-0000-0000-000000000002"
SENSOR_TEMP_2 = "30000000-0000-0000-0000-000000000003"
SENSOR_PRESS_2 = "30000000-0000-0000-0000-000000000004"
SENSOR_BATT_3 = "30000000-0000-0000-0000-000000000005"

# ── Sensor catalogue ─────────────────────────────────────────────
# Each entry pairs a config-key prefix with the deterministic
# device/sensor IDs and the *defaults* used when the operator hasn't
# customised the values via the UI. The runtime list of (device, sensor,
# lo, hi, interval) tuples is rebuilt on every ``start()`` from these
# specs + ``self._cfg``.

SENSOR_SPECS: list[tuple[str, str, str, float, float, float]] = [
    # (config_prefix, device_id, sensor_id, default_min, default_max, default_interval_s)
    ("living_room_temp", DEVICE_1, SENSOR_TEMP_1, 18.0, 28.0, 3.0),
    ("living_room_humidity", DEVICE_1, SENSOR_HUM_1, 30.0, 70.0, 3.0),
    ("weather_temp", DEVICE_2, SENSOR_TEMP_2, 15.0, 35.0, 3.0),
    ("weather_pressure", DEVICE_2, SENSOR_PRESS_2, 990.0, 1030.0, 3.0),
    ("door_battery", DEVICE_3, SENSOR_BATT_3, 3.0, 4.2, 15.0),
]

DEVICES = [
    {"device_id": DEVICE_1, "external_id": "test-device-01", "name": "Living Room Sensor", "location": "Living Room"},
    {"device_id": DEVICE_2, "external_id": "test-device-02", "name": "Outdoor Weather Station", "location": "Balcony"},
    {"device_id": DEVICE_3, "external_id": "test-device-03", "name": "Door Sensor", "location": "Front Door"},
]

SENSORS = [
    {"sensor_id": SENSOR_TEMP_1, "device_id": DEVICE_1, "key": "temperature", "name": "Temperature", "unit": "°C"},
    {"sensor_id": SENSOR_HUM_1, "device_id": DEVICE_1, "key": "humidity", "name": "Humidity", "unit": "%"},
    {"sensor_id": SENSOR_TEMP_2, "device_id": DEVICE_2, "key": "temperature", "name": "Temperature", "unit": "°C"},
    {
        "sensor_id": SENSOR_PRESS_2,
        "device_id": DEVICE_2,
        "key": "pressure",
        "name": "Atmospheric Pressure",
        "unit": "hPa",
    },
    {"sensor_id": SENSOR_BATT_3, "device_id": DEVICE_3, "key": "battery", "name": "Battery Voltage", "unit": "V"},
]

DEFAULT_TICK_INTERVAL_S = 1.0
DEFAULT_REGISTRATION_SETTLE_S = 3.0


class DemoSenderPlugin(DevicePlugin):
    """Generates random telemetry for demo / testing purposes."""

    name = "demo_sender"
    version = "0.1.0"

    def __init__(self) -> None:
        super().__init__()
        self._cfg: dict[str, Any] = {}

    async def configure(self, settings: dict[str, Any]) -> None:
        self._cfg = dict(settings or {})
        if self._cfg:
            logger.info(
                "Demo sender config loaded: tick=%.2fs, settle=%.2fs, %d sensor override(s)",
                float(self._cfg.get("tick_interval_s", DEFAULT_TICK_INTERVAL_S)),
                float(self._cfg.get("registration_settle_s", DEFAULT_REGISTRATION_SETTLE_S)),
                sum(
                    1
                    for prefix, *_rest in SENSOR_SPECS
                    for suffix in ("_min", "_max", "_interval_s")
                    if f"{prefix}{suffix}" in self._cfg
                ),
            )

    def _runtime_sensors(self) -> list[tuple[str, str, float, float, float]]:
        """Build the (device, sensor, lo, hi, interval) tuples from ``self._cfg``.

        Falls back to the spec defaults for any key the operator hasn't
        overridden. Coerces to ``float`` defensively in case a JSON value
        round-tripped as an int.
        """
        out: list[tuple[str, str, float, float, float]] = []
        for prefix, device_id, sensor_id, def_lo, def_hi, def_interval in SENSOR_SPECS:
            lo = float(self._cfg.get(f"{prefix}_min", def_lo))
            hi = float(self._cfg.get(f"{prefix}_max", def_hi))
            interval = float(self._cfg.get(f"{prefix}_interval_s", def_interval))
            out.append((device_id, sensor_id, lo, hi, interval))
        return out

    async def start(self) -> None:
        # ── 1. Register plugin, devices, sensors ────────────────
        await self._register()
        settle = float(
            self._cfg.get("registration_settle_s", DEFAULT_REGISTRATION_SETTLE_S)
        )
        logger.info(
            "Registration events sent — waiting %.1fs for the ingestor to process them …",
            settle,
        )
        await asyncio.sleep(settle)

        # ── 2. Publish synthetic telemetry on per-sensor cadences ─
        runtime_sensors = self._runtime_sensors()
        tick = float(self._cfg.get("tick_interval_s", DEFAULT_TICK_INTERVAL_S))
        logger.info(
            "Publishing synthetic telemetry — %d sensors, intervals %s s, tick=%.2fs",
            len(runtime_sensors),
            [round(s[4], 2) for s in runtime_sensors],
            tick,
        )
        last_emit_at: dict[str, datetime] = {}
        while True:
            now = datetime.now(UTC)
            emitted = 0
            for device_id, sensor_id, lo, hi, interval in runtime_sensors:
                last = last_emit_at.get(sensor_id)
                if last is not None and (now - last).total_seconds() < interval:
                    continue
                event = TelemetryEvent(
                    device_id=device_id,
                    sensor_id=sensor_id,
                    value=round(random.uniform(lo, hi), 2),
                    timestamp=now,
                )
                await self.ctx.publish_telemetry(event)
                last_emit_at[sensor_id] = now
                emitted += 1
            if emitted:
                logger.debug("Published %d synthetic events.", emitted)
            await asyncio.sleep(tick)

    async def stop(self) -> None:
        logger.info("Demo sender stopping.")

    def on_message(self, raw_data: bytes) -> list[TelemetryEvent]:
        """Not used — this plugin generates data internally."""
        return []

    # ── Internal helpers ────────────────────────────────────────

    async def _register(self) -> None:
        """Send idempotent registration events for this plugin's metadata."""
        await self.ctx.register_plugin()
        for dev in DEVICES:
            await self.ctx.register_device(**dev)
        for sens in SENSORS:
            await self.ctx.register_sensor(**sens)
