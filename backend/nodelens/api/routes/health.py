"""Health & readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens import __version__
from nodelens.api.deps import get_db
from nodelens.redis.client import get_redis
from nodelens.schemas.storage import (
    BudgetStatus,
    StoragePolicyConfig,
    StorageStats,
    TelemetrySize,
)
from nodelens.system_settings import runtime_settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    """Basic liveness check."""
    return {"status": "ok", "version": __version__}


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """Verify database connectivity."""
    result = await db.execute(text("SELECT 1"))
    row = result.scalar()
    return {"status": "ok" if row == 1 else "degraded", "version": __version__}


@router.get("/redis")
async def health_redis():
    """Verify Redis connectivity."""
    r = await get_redis()
    pong = await r.ping()
    return {"status": "ok" if pong else "degraded", "version": __version__}


@router.get("/storage")
async def health_storage(db: AsyncSession = Depends(get_db)) -> StorageStats:
    """Telemetry hypertable size, compression breakdown, and configured budget.

    Read-only view of the policies enforced by the ingestor (compression,
    retention, disk budget). The future settings UI will display this.
    """
    total_bytes = int(
        (await db.execute(text("SELECT hypertable_size('telemetry');"))).scalar() or 0
    )

    # `hypertable_compression_stats` returns one row per node. before/after are
    # NULL when no chunks have been compressed yet.
    stats_row = (
        await db.execute(
            text(
                "SELECT "
                "COALESCE(SUM(before_compression_total_bytes), 0) AS before_bytes, "
                "COALESCE(SUM(after_compression_total_bytes), 0)  AS after_bytes "
                "FROM hypertable_compression_stats('telemetry');"
            )
        )
    ).one()
    before_bytes = int(stats_row.before_bytes or 0)
    after_bytes = int(stats_row.after_bytes or 0)

    # Definitions:
    #   compressed_bytes   — physical bytes occupied by compressed chunks
    #   uncompressed_bytes — total - compressed (i.e. live recent chunks)
    #   compression_ratio  — original-size / on-disk-size for compressed chunks
    compressed_bytes = after_bytes
    uncompressed_bytes = max(total_bytes - compressed_bytes, 0)
    compression_ratio: float | None = None
    if before_bytes > 0 and after_bytes > 0:
        compression_ratio = round(before_bytes / after_bytes, 2)

    cfg = await runtime_settings.get_many(
        "retention_days",
        "compression_after_days",
        "disk_budget_gb",
        "retention_check_interval_seconds",
    )
    budget_bytes = int(cfg["disk_budget_gb"]) * 1024**3
    used_percent = round(100.0 * total_bytes / budget_bytes, 2) if budget_bytes else 0.0

    return StorageStats(
        telemetry=TelemetrySize(
            total_bytes=total_bytes,
            compressed_bytes=compressed_bytes,
            uncompressed_bytes=uncompressed_bytes,
            compression_ratio=compression_ratio,
        ),
        budget=BudgetStatus(
            budget_bytes=budget_bytes,
            used_bytes=total_bytes,
            used_percent=used_percent,
        ),
        config=StoragePolicyConfig(
            retention_days=cfg["retention_days"],
            compression_after_days=cfg["compression_after_days"],
            disk_budget_gb=cfg["disk_budget_gb"],
            retention_check_interval_seconds=cfg["retention_check_interval_seconds"],
        ),
    )
