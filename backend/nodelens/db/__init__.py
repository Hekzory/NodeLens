from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def init_models(engine: AsyncEngine) -> None:
    """Create all tables and convert telemetry to a TimescaleDB hypertable.

    Fully idempotent — safe to call on every startup.
    """
    from nodelens.db.base import Base

    # Force model registration so metadata.create_all sees every table.
    import nodelens.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);")
        )
