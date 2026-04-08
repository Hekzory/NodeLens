"""Unit tests for health API endpoints."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.health import router
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
