"""Shared fixtures for NodeLens unit tests."""

import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nodelens.system_settings import REGISTRY, runtime_settings

# ── Canonical test UUIDs ─────────────────────────────────────────
PLUGIN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
DEVICE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
SENSOR_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _seed_runtime_settings():
    """Pre-populate the in-process settings cache with registry defaults so tests
    don't try to hit a real DB through ``runtime_settings._reload``.

    Tests that want to override a value can mutate ``runtime_settings._cache``
    directly inside the test body — the autouse fixture restores defaults on
    teardown.
    """
    runtime_settings._cache = {k: spec.default for k, spec in REGISTRY.items()}
    runtime_settings._loaded_at = time.monotonic()
    yield
    runtime_settings.invalidate()

PLUGIN_ID_STR = str(PLUGIN_ID)
DEVICE_ID_STR = str(DEVICE_ID)
SENSOR_ID_STR = str(SENSOR_ID)


def make_execute_result(scalars_all=None, scalar_one_or_none=None, one=None):
    """Build a mock that mimics the result of AsyncSession.execute()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars_all or []
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar.return_value = 0
    if one is not None:
        result.one.return_value = one
    return result


def make_mock_db():
    """Return a mock AsyncSession suitable for API unit tests."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value=make_execute_result())
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=_refresh_side_effect)
    return db


async def _refresh_side_effect(obj):
    """Simulate DB refresh: set server-generated fields if not already set."""
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    now = datetime.now(UTC)
    if getattr(obj, "created_at", None) is None:
        obj.created_at = now
    if getattr(obj, "updated_at", None) is None:
        obj.updated_at = now
    if getattr(obj, "triggered_at", None) is None:
        obj.triggered_at = now


# ── Integration fixtures: real Postgres/Redis via testcontainers ──
# Session-scoped + lazy: containers start only when an integration test requests
# them. They SKIP (not fail) when Docker is unavailable, keeping `make test` green
# and the coverage gate intact (integration tests only add coverage).


@pytest.fixture(scope="session")
def postgres_url():
    """Ephemeral Postgres on a random host port; yields an asyncpg URL."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    try:
        with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
            yield pg.get_connection_url()
    except Exception as exc:  # noqa: BLE001 — any Docker failure → skip, don't fail
        pytest.skip(f"Postgres test container unavailable: {exc}")


@pytest.fixture(scope="session")
def redis_url():
    """Ephemeral Redis on a random host port; yields a redis:// URL."""
    try:
        from testcontainers.redis import RedisContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    try:
        with RedisContainer("redis:8-alpine") as rc:
            yield f"redis://{rc.get_container_host_ip()}:{rc.get_exposed_port(6379)}/0"
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis test container unavailable: {exc}")


@pytest.fixture(scope="session")
def timescale_url():
    """Ephemeral TimescaleDB (random host port) for the real-migration test.

    Uses the production image so Alembic's `create_hypertable` works; the cheaper
    plain-Postgres container above is enough for the create_all-based DB tests.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    try:
        with PostgresContainer("timescale/timescaledb:latest-pg17", driver="asyncpg") as pg:
            yield pg.get_connection_url()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"TimescaleDB test container unavailable: {exc}")


@pytest.fixture
async def db_sessionmaker(postgres_url):
    """Async sessionmaker bound to a freshly-created schema on the container DB."""
    import nodelens.db.models  # noqa: F401 — registers every table on Base.metadata
    from nodelens.db.base import Base

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def redis_conn(redis_url):
    """Async Redis client (decode_responses=True, matching production)."""
    conn = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await conn.flushdb()
        yield conn
    finally:
        await conn.aclose()
