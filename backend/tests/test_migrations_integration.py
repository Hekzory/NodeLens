"""Integration test: real Alembic migrations against TimescaleDB (testcontainers).

Verifies `init_models` brings up the full production schema — including the
TimescaleDB hypertable conversion that `Base.metadata.create_all` skips. Auto-
skipped when Docker is unavailable (see container fixture in conftest.py).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from nodelens.config import settings
from nodelens.db import init_models

pytestmark = pytest.mark.integration


async def test_init_models_builds_schema_and_hypertable(timescale_url, monkeypatch):
    """init_models runs the Alembic chain and converts telemetry to a hypertable."""
    # Alembic env.py + _alembic_config both read settings.DATABASE_URL at runtime.
    monkeypatch.setattr(settings, "DATABASE_URL", timescale_url)

    engine = create_async_engine(timescale_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))

        await init_models(engine)

        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT version_num FROM alembic_version"))
            assert await conn.scalar(text("SELECT to_regclass('public.plugins') IS NOT NULL")) is True
            hypertables = await conn.scalar(
                text(
                    "SELECT count(*) FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = 'telemetry'"
                )
            )
            assert hypertables == 1
    finally:
        await engine.dispose()
