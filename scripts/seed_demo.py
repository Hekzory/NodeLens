#!/usr/bin/env python
"""
Seed the database with a test plugin, three devices, and five sensors.

    docker compose run --rm seed          (via Makefile: make seed)

Idempotent — uses ``session.merge()`` so re-running updates existing rows
rather than failing on unique/PK conflicts.
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Ensure the backend package is importable when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from datetime import datetime, timezone  # noqa: E402

# ── Deterministic UUIDs — keep in sync with fake_publisher.py ──

TEST_PLUGIN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")

DEVICE_1 = uuid.UUID("20000000-0000-0000-0000-000000000001")
DEVICE_2 = uuid.UUID("20000000-0000-0000-0000-000000000002")
DEVICE_3 = uuid.UUID("20000000-0000-0000-0000-000000000003")

SENSOR_TEMP_1 = uuid.UUID("30000000-0000-0000-0000-000000000001")
SENSOR_HUM_1 = uuid.UUID("30000000-0000-0000-0000-000000000002")
SENSOR_TEMP_2 = uuid.UUID("30000000-0000-0000-0000-000000000003")
SENSOR_PRESS_2 = uuid.UUID("30000000-0000-0000-0000-000000000004")
SENSOR_BATT_3 = uuid.UUID("30000000-0000-0000-0000-000000000005")


async def main() -> None:
    from nodelens.db import init_models
    from nodelens.db.models import Device, Plugin, Sensor
    from nodelens.db.session import async_session, engine

    # Ensure tables exist (idempotent).
    await init_models(engine)

    now = datetime.now(timezone.utc)

    async with async_session() as session, session.begin():
        # ── Plugin ──
        await session.merge(
            Plugin(
                id=TEST_PLUGIN_ID,
                plugin_type="device",
                module_name="fake_test_source",
                display_name="Fake Test Source",
                version="0.0.1",
                is_active=True,
                created_at=now,
            )
        )

        # ── Devices ──
        await session.merge(
            Device(
                id=DEVICE_1,
                plugin_id=TEST_PLUGIN_ID,
                external_id="test-device-01",
                name="Living Room Sensor",
                location="Living Room",
                is_online=True,
                last_seen=now,
                created_at=now,
            )
        )
        await session.merge(
            Device(
                id=DEVICE_2,
                plugin_id=TEST_PLUGIN_ID,
                external_id="test-device-02",
                name="Outdoor Weather Station",
                location="Balcony",
                is_online=True,
                last_seen=now,
                created_at=now,
            )
        )
        await session.merge(
            Device(
                id=DEVICE_3,
                plugin_id=TEST_PLUGIN_ID,
                external_id="test-device-03",
                name="Door Sensor",
                location="Front Door",
                is_online=True,
                last_seen=now,
                created_at=now,
            )
        )

        # ── Sensors ──
        await session.merge(
            Sensor(
                id=SENSOR_TEMP_1,
                device_id=DEVICE_1,
                key="temperature",
                name="Temperature",
                unit="°C",
                value_type="numeric",
                created_at=now,
            )
        )
        await session.merge(
            Sensor(
                id=SENSOR_HUM_1,
                device_id=DEVICE_1,
                key="humidity",
                name="Humidity",
                unit="%",
                value_type="numeric",
                created_at=now,
            )
        )
        await session.merge(
            Sensor(
                id=SENSOR_TEMP_2,
                device_id=DEVICE_2,
                key="temperature",
                name="Temperature",
                unit="°C",
                value_type="numeric",
                created_at=now,
            )
        )
        await session.merge(
            Sensor(
                id=SENSOR_PRESS_2,
                device_id=DEVICE_2,
                key="pressure",
                name="Atmospheric Pressure",
                unit="hPa",
                value_type="numeric",
                created_at=now,
            )
        )
        await session.merge(
            Sensor(
                id=SENSOR_BATT_3,
                device_id=DEVICE_3,
                key="battery",
                name="Battery Voltage",
                unit="V",
                value_type="numeric",
                created_at=now,
            )
        )

    await engine.dispose()
    print("✔ Demo data seeded: 1 plugin, 3 devices, 5 sensors.")


if __name__ == "__main__":
    asyncio.run(main())
