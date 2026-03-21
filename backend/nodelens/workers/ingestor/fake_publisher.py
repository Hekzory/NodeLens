"""
Temporary synthetic data publisher.

Pushes random telemetry into the Redis stream so the ingest pipeline can be
verified end-to-end without real device plugins.

Sensor UUIDs here MUST match those created by ``scripts/seed_demo.py``.
Remove this file once the plugins-worker container is operational.
"""

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from nodelens.constants import TELEMETRY_STREAM
from nodelens.redis.client import get_redis
from nodelens.redis.streams import publish_event
from nodelens.schemas.events import TelemetryEvent

logger = logging.getLogger("nodelens.ingestor.fake_publisher")

# ── UUIDs must match scripts/seed_demo.py ──────────────────────

DEVICE_1 = uuid.UUID("20000000-0000-0000-0000-000000000001")
DEVICE_2 = uuid.UUID("20000000-0000-0000-0000-000000000002")
DEVICE_3 = uuid.UUID("20000000-0000-0000-0000-000000000003")

SENSOR_TEMP_1 = uuid.UUID("30000000-0000-0000-0000-000000000001")
SENSOR_HUM_1 = uuid.UUID("30000000-0000-0000-0000-000000000002")
SENSOR_TEMP_2 = uuid.UUID("30000000-0000-0000-0000-000000000003")
SENSOR_PRESS_2 = uuid.UUID("30000000-0000-0000-0000-000000000004")
SENSOR_BATT_3 = uuid.UUID("30000000-0000-0000-0000-000000000005")

# (device_uuid, sensor_uuid, value_min, value_max)
SYNTHETIC_SENSORS: list[tuple[uuid.UUID, uuid.UUID, float, float]] = [
    (DEVICE_1, SENSOR_TEMP_1, 18.0, 28.0),
    (DEVICE_1, SENSOR_HUM_1, 30.0, 70.0),
    (DEVICE_2, SENSOR_TEMP_2, 15.0, 35.0),
    (DEVICE_2, SENSOR_PRESS_2, 990.0, 1030.0),
    (DEVICE_3, SENSOR_BATT_3, 3.0, 4.2),
]

PUBLISH_INTERVAL_S = 3.0


async def run_fake_publisher() -> None:
    r = await get_redis()
    logger.info(
        "Fake publisher started — %d sensors every %.1fs",
        len(SYNTHETIC_SENSORS),
        PUBLISH_INTERVAL_S,
    )

    while True:
        now = datetime.now(timezone.utc)
        for device_uuid, sensor_uuid, lo, hi in SYNTHETIC_SENSORS:
            event = TelemetryEvent(
                device_id=str(device_uuid),
                sensor_id=str(sensor_uuid),
                value=round(random.uniform(lo, hi), 2),
                timestamp=now,
            )
            await publish_event(r, TELEMETRY_STREAM, event)

        logger.debug("Published %d synthetic events.", len(SYNTHETIC_SENSORS))
        await asyncio.sleep(PUBLISH_INTERVAL_S)
