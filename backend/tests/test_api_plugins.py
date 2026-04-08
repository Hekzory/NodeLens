"""Unit tests for plugin API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.plugins import router
from tests.conftest import DEVICE_ID, PLUGIN_ID, make_execute_result, make_mock_db

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


def _make_plugin():
    p = MagicMock()
    p.id = PLUGIN_ID
    p.plugin_type = "device"
    p.module_name = "demo_sender"
    p.display_name = "Demo Sender"
    p.version = "1.0.0"
    p.is_active = True
    p.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    return p


def _make_device():
    d = MagicMock()
    d.id = DEVICE_ID
    d.plugin_id = PLUGIN_ID
    d.external_id = "dev-001"
    d.name = "Test Device"
    d.location = None
    d.is_online = False
    d.last_seen = None
    d.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    d.sensors = []
    return d


class TestListPlugins:
    async def test_empty_list_returns_200(self, client, mock_db):
        result = make_execute_result()
        result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/plugins")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_plugins_with_device_count(self, client, mock_db):
        plugin = _make_plugin()
        result = make_execute_result()
        result.all.return_value = [(plugin, 3)]
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/plugins")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["module_name"] == "demo_sender"
        assert body[0]["device_count"] == 3


class TestGetPlugin:
    async def test_found_returns_plugin(self, client, mock_db):
        plugin = _make_plugin()
        result = make_execute_result()
        result.first.return_value = (plugin, 2)
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get(f"/api/plugins/{PLUGIN_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["module_name"] == "demo_sender"
        assert body["device_count"] == 2

    async def test_not_found_returns_404(self, client, mock_db):
        result = make_execute_result()
        result.first.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get(f"/api/plugins/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdatePlugin:
    async def test_toggle_is_active_returns_200(self, client, mock_db):
        plugin = _make_plugin()
        plugin.is_active = True
        mock_db.get = AsyncMock(return_value=plugin)
        result = make_execute_result()
        result.scalar.return_value = 1
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.patch(f"/api/plugins/{PLUGIN_ID}", json={"is_active": False})
        assert resp.status_code == 200
        assert plugin.is_active is False

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.patch(f"/api/plugins/{uuid.uuid4()}", json={"is_active": False})
        assert resp.status_code == 404


class TestListPluginDevices:
    async def test_plugin_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.get(f"/api/plugins/{uuid.uuid4()}/devices")
        assert resp.status_code == 404

    async def test_returns_devices_for_plugin(self, client, mock_db):
        plugin = _make_plugin()
        plugin.is_active = True
        device = _make_device()

        mock_db.get = AsyncMock(return_value=plugin)
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[device]))

        resp = await client.get(f"/api/plugins/{PLUGIN_ID}/devices")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Test Device"
        assert body[0]["sensor_count"] == 0
        assert body[0]["is_online"] is False  # last_seen is None
