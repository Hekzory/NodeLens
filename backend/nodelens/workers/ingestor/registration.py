"""Consumes registration events from Redis and upserts plugins/devices/sensors into the DB.

Registration is **idempotent** — every event is an upsert (INSERT … ON CONFLICT
DO UPDATE).  Plugins re-send their full registration set on every start, so
missed events are self-healing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from nodelens.constants import (
    REGISTRATION_CONSUMER_GROUP,
    REGISTRATION_CONSUMER_NAME,
    REGISTRATION_STREAM,
)
from nodelens.db.models import Device, Plugin, Sensor
from nodelens.db.session import async_session
from nodelens.redis.client import get_redis
from nodelens.redis.streams import ack, ensure_consumer_group, read_stream
from nodelens.schemas.events import (
    RegisterDeviceEvent,
    RegisterPluginEvent,
    RegisterSensorEvent,
)

logger = logging.getLogger("nodelens.ingestor.registration")

_HEARTBEAT = Path("/tmp/.healthcheck")


# ── Parsers ─────────────────────────────────────────────────────


def _parse_register_plugin(fields: dict) -> RegisterPluginEvent:
    return RegisterPluginEvent(
        plugin_id=fields["plugin_id"],
        plugin_type=fields["plugin_type"],
        module_name=fields["module_name"],
        display_name=fields["display_name"],
        version=fields["version"],
    )


def _parse_register_device(fields: dict) -> RegisterDeviceEvent:
    return RegisterDeviceEvent(
        device_id=fields["device_id"],
        plugin_id=fields["plugin_id"],
        external_id=fields["external_id"],
        name=fields["name"],
        location=fields.get("location", ""),
    )


def _parse_register_sensor(fields: dict) -> RegisterSensorEvent:
    return RegisterSensorEvent(
        sensor_id=fields["sensor_id"],
        device_id=fields["device_id"],
        key=fields["key"],
        name=fields["name"],
        unit=fields.get("unit", ""),
        value_type=fields.get("value_type", "numeric"),
    )


# ── Main loop ───────────────────────────────────────────────────


async def run_registration_consumer() -> None:
    """Main loop: read registration_events, upsert into Postgres, ACK."""
    r = await get_redis()
    await ensure_consumer_group(r, REGISTRATION_STREAM, REGISTRATION_CONSUMER_GROUP)
    logger.info(
        "Registration consumer started  stream=%s  group=%s",
        REGISTRATION_STREAM,
        REGISTRATION_CONSUMER_GROUP,
    )

    while True:
        try:
            messages = await read_stream(
                r,
                group=REGISTRATION_CONSUMER_GROUP,
                consumer=REGISTRATION_CONSUMER_NAME,
                stream=REGISTRATION_STREAM,
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

        for msg_id, fields in messages:
            try:
                event_type = fields.get("event_type", "")
                if event_type == "register_plugin":
                    event_p = _parse_register_plugin(fields)
                    await _upsert_plugin(event_p)
                    logger.info("Registered plugin: %s (id=%s)", event_p.module_name, event_p.plugin_id)
                elif event_type == "register_device":
                    event_d = _parse_register_device(fields)
                    await _upsert_device(event_d)
                    logger.info("Registered device: %s (id=%s)", event_d.name, event_d.device_id)
                elif event_type == "register_sensor":
                    event_s = _parse_register_sensor(fields)
                    await _upsert_sensor(event_s)
                    logger.info(
                        "Registered sensor: %s on device %s",
                        event_s.key,
                        event_s.device_id[:8],
                    )
                else:
                    logger.warning("Unknown registration event_type=%s  msg=%s", event_type, msg_id)
            except Exception:
                logger.exception("Failed to process registration event %s", msg_id)
            # Always ACK — registration is idempotent; plugins re-register on restart.
            await ack(r, REGISTRATION_STREAM, REGISTRATION_CONSUMER_GROUP, msg_id)


# ── Upsert helpers ──────────────────────────────────────────────


async def _upsert_plugin(event: RegisterPluginEvent) -> None:
    plugin_id = uuid.UUID(event.plugin_id)
    values = {
        "id": plugin_id,
        "plugin_type": event.plugin_type,
        "module_name": event.module_name,
        "display_name": event.display_name,
        "version": event.version,
        "is_active": True,
    }
    async with async_session() as session, session.begin():
        stmt = (
            pg_insert(Plugin)
            .values(values)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "display_name": values["display_name"],
                    "version": values["version"],
                },
            )
        )
        await session.execute(stmt)


async def _upsert_device(event: RegisterDeviceEvent) -> None:
    device_id = uuid.UUID(event.device_id)
    plugin_id = uuid.UUID(event.plugin_id)
    location = event.location or None
    values = {
        "id": device_id,
        "plugin_id": plugin_id,
        "external_id": event.external_id,
        "name": event.name,
        "location": location,
    }
    async with async_session() as session, session.begin():
        stmt = (
            pg_insert(Device)
            .values(values)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "external_id": values["external_id"],
                    "name": values["name"],
                    "location": values["location"],
                },
            )
        )
        await session.execute(stmt)


async def _upsert_sensor(event: RegisterSensorEvent) -> None:
    sensor_id = uuid.UUID(event.sensor_id)
    device_id = uuid.UUID(event.device_id)
    unit = event.unit or None
    values = {
        "id": sensor_id,
        "device_id": device_id,
        "key": event.key,
        "name": event.name,
        "unit": unit,
        "value_type": event.value_type,
    }
    async with async_session() as session, session.begin():
        stmt = (
            pg_insert(Sensor)
            .values(values)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "key": values["key"],
                    "name": values["name"],
                    "unit": values["unit"],
                    "value_type": values["value_type"],
                },
            )
        )
        await session.execute(stmt)
