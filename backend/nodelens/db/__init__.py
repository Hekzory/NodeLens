import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from nodelens.config import settings


def _alembic_config() -> Config:
    """Build an Alembic Config pointing at backend/alembic.ini."""
    backend_root = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg


async def init_models(engine: AsyncEngine) -> None:
    """Bring the database schema up to date via Alembic.

    Auto-stamps existing pre-Alembic deployments to the baseline so the first
    real migration runs cleanly. Idempotent: safe to call on every startup.
    """
    cfg = _alembic_config()

    # Pre-Alembic deployments: schema exists, alembic_version doesn't.
    # Stamp baseline first so the upgrade only runs migrations after it.
    async with engine.connect() as conn:
        has_alembic = await conn.scalar(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        )
        has_plugins = await conn.scalar(
            text("SELECT to_regclass('public.plugins') IS NOT NULL")
        )

    if has_plugins and not has_alembic:
        await asyncio.to_thread(command.stamp, cfg, "0001_baseline")

    await asyncio.to_thread(command.upgrade, cfg, "head")


async def apply_storage_policies(engine: AsyncEngine) -> None:
    """Enable columnar compression + (re-)apply compression and retention policies.

    Reads `compression_after_days` and `retention_days` via `runtime_settings`
    (DB override falls through to `nodelens.config.settings` defaults). Each
    call drops the existing policies and recreates them so edits take effect on
    restart. Idempotent: safe to invoke on every startup.

    Owned by the ingestor process (it owns telemetry writes); other workers should
    not call this.
    """
    # Deferred import: nodelens.system_settings.service depends on nodelens.db.models,
    # so a top-level import here would close the cycle through this very module.
    from nodelens.system_settings import runtime_settings

    cfg = await runtime_settings.get_many("compression_after_days", "retention_days")
    compress_days = int(cfg["compression_after_days"])
    retain_days = int(cfg["retention_days"])

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
