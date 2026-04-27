"""Unit tests for health API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.health import router
from nodelens.config import settings
from tests.conftest import make_execute_result, make_mock_db

_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def mock_db():
    return make_mock_db()


@pytest.fixture
async def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _app.dependency_overrides.clear()


class TestHealth:
    async def test_liveness_returns_ok(self, client, mock_db):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_db_health_returns_ok(self, client, mock_db):
        result = make_execute_result()
        result.scalar.return_value = 1
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/health/db")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def _storage_execute_factory(*, total_bytes: int, before_bytes: int, after_bytes: int):
    """Build an execute() side_effect that routes by SQL substring."""

    async def _execute(stmt, *_a, **_kw):
        sql = str(stmt)
        result = MagicMock()
        if "hypertable_size" in sql:
            result.scalar = MagicMock(return_value=total_bytes)
        elif "hypertable_compression_stats" in sql:
            row = MagicMock(before_bytes=before_bytes, after_bytes=after_bytes)
            result.one = MagicMock(return_value=row)
        else:
            result.scalar = MagicMock(return_value=None)
        return result

    return _execute


class TestStorage:
    async def test_returns_config_from_settings(self, client, mock_db):
        mock_db.execute = AsyncMock(
            side_effect=_storage_execute_factory(total_bytes=0, before_bytes=0, after_bytes=0)
        )

        resp = await client.get("/api/health/storage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["config"] == {
            "retention_days": settings.RETENTION_DAYS,
            "compression_after_days": settings.COMPRESSION_AFTER_DAYS,
            "disk_budget_gb": settings.DISK_BUDGET_GB,
            "retention_check_interval_seconds": settings.RETENTION_CHECK_INTERVAL_SECONDS,
        }

    async def test_handles_no_compressed_chunks_yet(self, client, mock_db):
        mock_db.execute = AsyncMock(
            side_effect=_storage_execute_factory(total_bytes=1024, before_bytes=0, after_bytes=0)
        )

        resp = await client.get("/api/health/storage")
        body = resp.json()
        assert body["telemetry"]["compressed_bytes"] == 0
        assert body["telemetry"]["uncompressed_bytes"] == 1024
        assert body["telemetry"]["compression_ratio"] is None

    async def test_computes_used_percent_and_ratio(self, client, mock_db):
        gb = 1024**3
        mock_db.execute = AsyncMock(
            side_effect=_storage_execute_factory(
                total_bytes=3 * gb,
                before_bytes=10 * gb,
                after_bytes=2 * gb,
            )
        )

        resp = await client.get("/api/health/storage")
        body = resp.json()
        assert body["telemetry"]["compressed_bytes"] == 2 * gb
        assert body["telemetry"]["uncompressed_bytes"] == (3 * gb) - (2 * gb)
        assert body["telemetry"]["compression_ratio"] == 5.0  # 10 / 2
        budget_bytes = settings.DISK_BUDGET_GB * gb
        expected_pct = round(100.0 * (3 * gb) / budget_bytes, 2)
        assert body["budget"]["used_bytes"] == 3 * gb
        assert body["budget"]["budget_bytes"] == budget_bytes
        assert body["budget"]["used_percent"] == expected_pct
