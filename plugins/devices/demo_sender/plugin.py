"""
Demo device plugin — generates synthetic telemetry data.

Replaces the old ``fake_publisher`` that was embedded in the ingestor.
Registers its own plugin record, devices, and sensors via the
registration stream, then publishes random values at a fixed interval.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
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

# (device_id, sensor_id, value_min, value_max)
SYNTHETIC_SENSORS: list[tuple[str, str, float, float]] = [
    (DEVICE_1, SENSOR_TEMP_1, 18.0, 28.0),
    (DEVICE_1, SENSOR_HUM_1, 30.0, 70.0),
    (DEVICE_2, SENSOR_TEMP_2, 15.0, 35.0),
    (DEVICE_2, SENSOR_PRESS_2, 990.0, 1030.0),
    (DEVICE_3, SENSOR_BATT_3, 3.0, 4.2),
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

PUBLISH_INTERVAL_S = 3.0
REGISTRATION_SETTLE_S = 3.0


class DemoSenderPlugin(DevicePlugin):
    """Generates random telemetry for demo / testing purposes."""

    name = "demo_sender"
    version = "0.1.0"

    async def configure(self, settings: dict[str, Any]) -> None:
        """No extra configuration needed for the demo plugin."""

    async def start(self) -> None:
        # ── 1. Register plugin, devices, sensors ────────────────
        await self._register()
        logger.info(
            "Registration events sent — waiting %.0fs for the ingestor to process them …",
            REGISTRATION_SETTLE_S,
        )
        await asyncio.sleep(REGISTRATION_SETTLE_S)

        # ── 2. Publish synthetic telemetry ──────────────────────
        logger.info(
            "Publishing synthetic telemetry — %d sensors every %.1fs",
            len(SYNTHETIC_SENSORS),
            PUBLISH_INTERVAL_S,
        )
        while True:
            now = datetime.now(timezone.utc)
            for device_id, sensor_id, lo, hi in SYNTHETIC_SENSORS:
                event = TelemetryEvent(
                    device_id=device_id,
                    sensor_id=sensor_id,
                    value=round(random.uniform(lo, hi), 2),
                    timestamp=now,
                )
                await self.ctx.publish_telemetry(event)
            logger.debug("Published %d synthetic events.", len(SYNTHETIC_SENSORS))
            await asyncio.sleep(PUBLISH_INTERVAL_S)

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
