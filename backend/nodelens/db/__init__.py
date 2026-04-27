from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nodelens.config import settings


async def init_models(engine: AsyncEngine) -> None:
    """Create all tables and convert telemetry to a TimescaleDB hypertable.

    Fully idempotent — safe to call on every startup.
    """
    # Force model registration so metadata.create_all sees every table.
    import nodelens.db.models  # noqa: F401
    from nodelens.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);")
        )


async def apply_storage_policies(engine: AsyncEngine) -> None:
    """Enable columnar compression + (re-)apply compression and retention policies.

    Reads `COMPRESSION_AFTER_DAYS` and `RETENTION_DAYS` from `settings`. Each call
    drops the existing policies and recreates them so config edits take effect on
    restart. Idempotent: safe to invoke on every startup.

    Owned by the ingestor process (it owns telemetry writes); other workers should
    not call this.
    """
    compress_days = int(settings.COMPRESSION_AFTER_DAYS)
    retain_days = int(settings.RETENTION_DAYS)

    async with engine.begin() as conn:
        # Enable per-sensor columnar compression. segmentby=sensor_id matches the
        # access pattern in routes/telemetry.py (every query filters by sensor_id).
        # Re-running this with the same options is a Postgres no-op.
        await conn.execute(
            text(
                "ALTER TABLE telemetry SET ("
                "timescaledb.compress, "
                "timescaledb.compress_segmentby = 'sensor_id', "
                "timescaledb.compress_orderby = 'time DESC'"
                ");"
            )
        )

        await conn.execute(
            text("SELECT remove_compression_policy('telemetry', if_exists => TRUE);")
        )
        await conn.execute(
            text(
                f"SELECT add_compression_policy('telemetry', compress_after => INTERVAL '{compress_days} days');"
            )
        )

        await conn.execute(
            text("SELECT remove_retention_policy('telemetry', if_exists => TRUE);")
        )
        await conn.execute(
            text(
                f"SELECT add_retention_policy('telemetry', drop_after => INTERVAL '{retain_days} days');"
            )
        )
