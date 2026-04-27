"""Disk-budget enforcer for the telemetry hypertable.

Runs inside the ingestor process. Periodically checks total telemetry size; when
it exceeds `DISK_BUDGET_GB`, drops oldest chunks until projected usage is back
under 95% of the budget. This complements (does not replace) Timescale's
built-in retention policy: the policy enforces the *time* bound, this enforces
the *space* bound.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from nodelens.config import settings
from nodelens.db.session import async_session
from nodelens.heartbeat import touch_heartbeat

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nodelens.ingestor.retention")

# Drop chunks until projected usage is at or below this fraction of the budget.
# Headroom prevents oscillation when chunks are large.
HEADROOM_FRACTION = 0.95


@dataclass(frozen=True, slots=True)
class ChunkInfo:
    range_end: datetime
    total_bytes: int


def select_chunks_to_drop(
    total_bytes: int,
    budget_bytes: int,
    chunks_oldest_first: list[ChunkInfo],
) -> datetime | None:
    """Pure decision: which `older_than` cutoff to pass to drop_chunks().

    Returns the `range_end` of the newest chunk to drop, or None if no drop is
    needed. Caller passes the result as `older_than =>` to drop_chunks(), which
    treats the bound as exclusive of the cutoff range_start of remaining chunks.
    """
    if budget_bytes <= 0:
        # Degenerate config — drop everything we can see.
        return chunks_oldest_first[-1].range_end if chunks_oldest_first else None
    if total_bytes <= budget_bytes:
        return None

    target = int(budget_bytes * HEADROOM_FRACTION)
    projected = total_bytes
    cutoff: datetime | None = None
    for chunk in chunks_oldest_first:
        if projected <= target:
            break
        cutoff = chunk.range_end
        projected -= chunk.total_bytes
    return cutoff


async def _hypertable_size(session: AsyncSession) -> int:
    row = (await session.execute(text("SELECT hypertable_size('telemetry');"))).scalar()
    return int(row or 0)


async def _list_chunks_oldest_first(session: AsyncSession) -> list[ChunkInfo]:
    rows = (
        await session.execute(
            text(
                "SELECT range_end, total_bytes FROM chunks_detailed_size('telemetry') "
                "ORDER BY range_end ASC;"
            )
        )
    ).all()
    return [ChunkInfo(range_end=r.range_end, total_bytes=int(r.total_bytes or 0)) for r in rows]


async def _drop_chunks_older_than(session: AsyncSession, cutoff: datetime) -> None:
    await session.execute(
        text("SELECT drop_chunks('telemetry', older_than => :cutoff);"),
        {"cutoff": cutoff},
    )


async def enforce_once() -> None:
    """One enforcement tick. Public so tests can drive it without the loop."""
    budget_bytes = int(settings.DISK_BUDGET_GB) * 1024**3

    async with async_session() as session, session.begin():
        total = await _hypertable_size(session)
        if total <= budget_bytes:
            logger.debug("Disk budget OK: %d / %d bytes (%.1f%%)",
                         total, budget_bytes, 100.0 * total / max(budget_bytes, 1))
            return

        chunks = await _list_chunks_oldest_first(session)
        cutoff = select_chunks_to_drop(total, budget_bytes, chunks)
        if cutoff is None:
            logger.warning(
                "Telemetry size %d > budget %d but no droppable chunks were found.",
                total, budget_bytes,
            )
            return

        await _drop_chunks_older_than(session, cutoff)
        logger.warning(
            "Disk budget exceeded (%d > %d bytes) — dropped chunks older than %s.",
            total, budget_bytes, cutoff.isoformat(),
        )


async def run_disk_budget_enforcer() -> None:
    """Periodic loop. Sleeps first so it does not race startup tasks."""
    interval = int(settings.RETENTION_CHECK_INTERVAL_SECONDS)
    logger.info(
        "Disk-budget enforcer started  budget=%dGB  interval=%ds",
        settings.DISK_BUDGET_GB, interval,
    )
    while True:
        await asyncio.sleep(interval)
        try:
            await enforce_once()
        except Exception:
            logger.exception("Disk-budget enforcement tick failed; will retry on next interval.")
        touch_heartbeat()
