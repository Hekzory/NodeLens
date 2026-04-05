"""
Writes TelemetryEvent batches into the telemetry hypertable.

Validates that:
- ``sensor_id`` and ``device_id`` are valid UUIDs
- ``sensor_id`` exists in the ``sensors`` table
- ``sensor_id`` belongs to the specified ``device_id``
- ``device_id`` exists and has a registered plugin (FK guarantees this)

After a successful write, updates ``devices.last_seen`` to the latest
event timestamp observed for each affected device.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from nodelens.db.models.device import Device
from nodelens.db.models.plugin import Plugin
from nodelens.db.models.sensor import Sensor
from nodelens.db.models.telemetry import TelemetryRecord
from nodelens.db.session import async_session
from nodelens.schemas.events import TelemetryEvent

logger = logging.getLogger("nodelens.ingestor.writer")


async def write_batch(events: list[TelemetryEvent]) -> int:
    """Validate, insert, and update ``last_seen`` for a batch of telemetry events.

    Returns the number of rows actually written.
    Events that fail validation are logged and skipped.
    """
    # ── 1. Parse UUIDs ──────────────────────────────────────────
    parsed: list[tuple[TelemetryEvent, uuid.UUID, uuid.UUID]] = []
    for ev in events:
        try:
            sid = uuid.UUID(ev.sensor_id)
            did = uuid.UUID(ev.device_id)
            parsed.append((ev, sid, did))
        except ValueError:
            logger.warning(
                "Skipping event — invalid UUID: sensor_id=%s device_id=%s",
                ev.sensor_id,
                ev.device_id,
            )

    if not parsed:
        return 0

    sensor_ids = {sid for _, sid, _ in parsed}
    device_ids = {did for _, _, did in parsed}

    # ── 2. Load mappings from DB ────────────────────────────────
    sensor_device_map, valid_device_ids = await _load_mappings(sensor_ids, device_ids)

    # ── 3. Validate each event ──────────────────────────────────
    valid_rows: list[dict] = []
    affected_devices: dict[uuid.UUID, datetime] = {}

    for ev, sid, did in parsed:
        if sid not in sensor_device_map:
            logger.debug("Skipping event — sensor_id %s not found in DB.", sid)
            continue

        owning_device = sensor_device_map[sid]
        if owning_device != did:
            logger.warning(
                "Skipping event — sensor %s belongs to device %s, not %s.",
                sid,
                owning_device,
                did,
            )
            continue

        if did not in valid_device_ids:
            logger.debug("Skipping event — device %s not found or has no registered plugin.", did)
            continue

        valid_rows.append(
            {
                "time": ev.timestamp,
                "sensor_id": sid,
                "value_numeric": ev.value,
                "value_text": None,
            }
        )

        if did not in affected_devices or ev.timestamp > affected_devices[did]:
            affected_devices[did] = ev.timestamp

    if not valid_rows:
        return 0

    # ── 4. Insert valid rows ────────────────────────────────────
    try:
        written = await _insert_rows(valid_rows)
    except IntegrityError:
        logger.warning("Batch insert hit IntegrityError — falling back to per-row insert.")
        written = await _insert_rows_individually(valid_rows)

    # ── 5. Update last_seen for affected devices ────────────────
    if affected_devices and written > 0:
        await _update_last_seen(affected_devices)

    return written


# ── DB helpers ──────────────────────────────────────────────────


async def _load_mappings(
    sensor_ids: set[uuid.UUID],
    device_ids: set[uuid.UUID],
) -> tuple[dict[uuid.UUID, uuid.UUID], set[uuid.UUID]]:
    """Query DB for sensor→device mapping and valid device IDs.

    Returns:
        sensor_device_map: ``{sensor_id: device_id}`` for sensors that exist.
        valid_device_ids:  set of device_ids that exist and whose plugin is active.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Sensor.id, Sensor.device_id).where(Sensor.id.in_(sensor_ids))
        )
        sensor_device_map: dict[uuid.UUID, uuid.UUID] = {row.id: row.device_id for row in result}

        result = await session.execute(
            select(Device.id)
            .join(Plugin, Device.plugin_id == Plugin.id)
            .where(Device.id.in_(device_ids), Plugin.is_active.is_(True))
        )
        valid_device_ids: set[uuid.UUID] = {row.id for row in result}

    return sensor_device_map, valid_device_ids


async def _insert_rows(rows: list[dict]) -> int:
    async with async_session() as session, session.begin():
        stmt = (
            pg_insert(TelemetryRecord)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["time", "sensor_id"])
        )
        result = await session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]


async def _insert_rows_individually(rows: list[dict]) -> int:
    written = 0
    for row in rows:
        try:
            async with async_session() as session, session.begin():
                stmt = (
                    pg_insert(TelemetryRecord)
                    .values([row])
                    .on_conflict_do_nothing(index_elements=["time", "sensor_id"])
                )
                result = await session.execute(stmt)
                written += result.rowcount  # type: ignore[operator]
        except IntegrityError:
            logger.debug(
                "Skipped row — integrity error for sensor_id %s.",
                row["sensor_id"],
            )
    return written


async def _update_last_seen(affected_devices: dict[uuid.UUID, datetime]) -> None:
    """Set ``devices.last_seen`` to the latest observed timestamp.

    Only updates when the new timestamp is more recent than the stored one
    (or when ``last_seen`` is NULL), so out-of-order events are harmless.
    """
    async with async_session() as session, session.begin():
        for device_id, latest_ts in affected_devices.items():
            await session.execute(
                update(Device)
                .where(Device.id == device_id)
                .where(or_(Device.last_seen.is_(None), Device.last_seen < latest_ts))
                .values(last_seen=latest_ts)
            )
