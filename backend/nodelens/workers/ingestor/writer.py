"""
Writes TelemetryEvent batches into the telemetry hypertable.

The writer is intentionally simple — it does NOT create devices, sensors, or
plugins.  Those must already exist in the database (see ``scripts/seed_demo.py``
or, later, the plugins-worker).  Rows that reference a non-existent sensor_id
are logged and skipped.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from nodelens.db.models.telemetry import TelemetryRecord
from nodelens.db.session import async_session
from nodelens.schemas.events import TelemetryEvent

logger = logging.getLogger("nodelens.ingestor.writer")


async def write_batch(events: list[TelemetryEvent]) -> int:
    """Insert a batch of telemetry rows.

    Returns the number of rows actually written (excluding duplicates).
    Rows with unknown ``sensor_id`` cause the batch to be retried one-by-one
    so valid rows are not lost.
    """
    rows = [
        {
            "time": ev.timestamp,
            "sensor_id": uuid.UUID(ev.sensor_id),
            "value_numeric": ev.value,
            "value_text": None,
        }
        for ev in events
    ]

    try:
        return await _insert_rows(rows)
    except IntegrityError:
        # Likely an FK violation (sensor_id not in sensors table).
        # Fall back to one-by-one so valid rows still land.
        logger.warning("Batch insert hit IntegrityError — falling back to per-row insert.")
        return await _insert_rows_individually(rows)


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
                "Skipped row — sensor_id %s not found in sensors table.", row["sensor_id"]
            )
    return written
