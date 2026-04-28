"""Unit tests for plugin API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

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


def _make_plugin(description: str | None = "Demo plugin description"):
    p = MagicMock()
    p.id = PLUGIN_ID
    p.plugin_type = "device"
    p.module_name = "demo_sender"
    p.display_name = "Demo Sender"
    p.description = description
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
        assert body[0]["description"] == "Demo plugin description"

    async def test_null_description_passes_through(self, client, mock_db):
        plugin = _make_plugin(description=None)
        result = make_execute_result()
        result.all.return_value = [(plugin, 0)]
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/plugins")
        assert resp.status_code == 200
        assert resp.json()[0]["description"] is None


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
        assert body["description"] == "Demo plugin description"

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

    async def test_duplicate_module_name_returns_409(self, client, mock_db):
        plugin = _make_plugin()
        mock_db.get = AsyncMock(return_value=plugin)
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("duplicate", params=None, orig=Exception())
        )
        resp = await client.patch(
            f"/api/plugins/{PLUGIN_ID}", json={"display_name": "Taken Name"}
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


def _make_plugin_with_config(
    *,
    config: dict | None = None,
    config_schema: list[dict] | None = None,
    config_version: int = 0,
):
    p = _make_plugin()
    p.config = config or {}
    p.config_schema = config_schema or [
        {"key": "host", "label": "SMTP host", "group": "connection",
         "value_type": "string", "default": "localhost",
         "help": "", "unit": None, "min": None, "max": None,
         "requires_restart": False},
        {"key": "port", "label": "SMTP port", "group": "connection",
         "value_type": "int", "default": 25,
         "help": "", "unit": None, "min": 1.0, "max": 65535.0,
         "requires_restart": False},
        {"key": "pwd", "label": "Password", "group": "connection",
         "value_type": "secret", "default": "",
         "help": "", "unit": None, "min": None, "max": None,
         "requires_restart": False},
    ]
    p.config_version = config_version
    return p


class TestGetPluginConfig:
    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.get(f"/api/plugins/{uuid.uuid4()}/config")
        assert resp.status_code == 404

    async def test_returns_schema_and_default_values(self, client, mock_db):
        plugin = _make_plugin_with_config()
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.get(f"/api/plugins/{PLUGIN_ID}/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["config_version"] == 0
        keys = [f["key"] for f in body["fields"]]
        assert keys == ["host", "port", "pwd"]
        # All defaults → is_default true everywhere
        assert all(f["is_default"] for f in body["fields"])
        # Secret default is nulled, not echoed
        pwd = next(f for f in body["fields"] if f["key"] == "pwd")
        assert pwd["value"] is None
        assert pwd["default"] is None

    async def test_overridden_secret_is_masked(self, client, mock_db):
        plugin = _make_plugin_with_config(
            config={"pwd": "hunter2", "host": "smtp.test"},
            config_version=3,
        )
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.get(f"/api/plugins/{PLUGIN_ID}/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["config_version"] == 3
        pwd = next(f for f in body["fields"] if f["key"] == "pwd")
        assert pwd["value"] == "••••••"
        assert pwd["is_default"] is False
        host = next(f for f in body["fields"] if f["key"] == "host")
        assert host["value"] == "smtp.test"
        assert host["is_default"] is False
        # Real password never appears anywhere in the response body
        assert "hunter2" not in resp.text


class TestUpdatePluginConfig:
    async def test_empty_updates_returns_422(self, client, mock_db):
        resp = await client.patch(
            f"/api/plugins/{PLUGIN_ID}/config", json={"updates": {}}
        )
        assert resp.status_code == 422

    async def test_unknown_field_returns_422_with_field_errors(self, client, mock_db):
        plugin = _make_plugin_with_config()
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.patch(
            f"/api/plugins/{PLUGIN_ID}/config",
            json={"updates": {"made_up": "x"}},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "field_errors" in detail
        assert "made_up" in detail["field_errors"]

    async def test_valid_update_returns_response_with_bumped_version(
        self, client, mock_db
    ):
        # On entry the plugin has config_version=0; after the UPDATE statement
        # the re-read still goes through mock_db.get which returns the same
        # MagicMock — so we simulate the version bump by mutating the mock
        # after the first get() call.
        plugin = _make_plugin_with_config()
        get_calls = {"n": 0}

        async def get_side_effect(_model, _pid):
            get_calls["n"] += 1
            if get_calls["n"] >= 2:
                plugin.config = {**plugin.config, "host": "smtp.example"}
                plugin.config_version = 1
            return plugin

        mock_db.get = AsyncMock(side_effect=get_side_effect)
        resp = await client.patch(
            f"/api/plugins/{PLUGIN_ID}/config",
            json={"updates": {"host": "smtp.example"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["config"]["config_version"] == 1
        host = next(f for f in body["config"]["fields"] if f["key"] == "host")
        assert host["value"] == "smtp.example"
        assert host["is_default"] is False
        assert mock_db.commit.await_count == 1

    async def test_plugin_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.patch(
            f"/api/plugins/{uuid.uuid4()}/config",
            json={"updates": {"host": "x"}},
        )
        assert resp.status_code == 404


class TestResetPluginConfig:
    async def test_reset_all_returns_204(self, client, mock_db):
        plugin = _make_plugin_with_config(config={"host": "x"})
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.delete(f"/api/plugins/{PLUGIN_ID}/config")
        assert resp.status_code == 204
        assert mock_db.commit.await_count == 1

    async def test_reset_single_key_returns_204(self, client, mock_db):
        plugin = _make_plugin_with_config(config={"host": "x", "port": 9})
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.delete(
            f"/api/plugins/{PLUGIN_ID}/config?key=host"
        )
        assert resp.status_code == 204

    async def test_unknown_plugin_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.delete(f"/api/plugins/{uuid.uuid4()}/config")
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
