"""Unit tests for the notification channels API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from nodelens.api.deps import get_db
from nodelens.api.routes.channels import router
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


def _integration_plugin(pid: uuid.UUID | None = None):
    p = MagicMock()
    p.id = pid or uuid.uuid4()
    p.plugin_type = "integration"
    p.module_name = "email"
    p.display_name = "Email"
    return p


def _device_plugin(pid: uuid.UUID | None = None):
    p = MagicMock()
    p.id = pid or uuid.uuid4()
    p.plugin_type = "device"
    p.module_name = "demo"
    return p


def _channel():
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.name = "Test channel"
    ch.plugin_id = uuid.uuid4()
    ch.plugin_module_name = None  # populated by route's _to_read; prevent MagicMock leak
    ch.config = {"to": "x@y.z"}
    ch.is_active = True
    ch.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    ch.updated_at = datetime(2024, 1, 1, tzinfo=UTC)
    return ch


_BASE_BODY = {
    "name": "ops",
    "plugin_id": str(uuid.uuid4()),
    "config": {"to": "ops@example.com"},
}


class TestCreateChannel:
    async def test_unknown_plugin_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.post("/api/alerts/channels", json=_BASE_BODY)
        assert resp.status_code == 400
        assert "Plugin" in resp.json()["detail"]

    async def test_device_plugin_rejected(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=_device_plugin())
        resp = await client.post("/api/alerts/channels", json=_BASE_BODY)
        assert resp.status_code == 400
        assert "integration" in resp.json()["detail"].lower()

    async def test_happy_path(self, client, mock_db):
        plugin = _integration_plugin()
        # First db.get: validate plugin (integration). Second db.get: _to_read fetch plugin again.
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.post("/api/alerts/channels", json=_BASE_BODY)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "ops"
        assert body["plugin_module_name"] == "email"

    async def test_duplicate_name_returns_409(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=_integration_plugin())
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("duplicate", params=None, orig=Exception())
        )
        resp = await client.post("/api/alerts/channels", json=_BASE_BODY)
        assert resp.status_code == 409


class TestListChannels:
    async def test_empty(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/alerts/channels")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_rows(self, client, mock_db):
        ch = _channel()
        plugin = _integration_plugin(ch.plugin_id)
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[ch]))
        mock_db.get = AsyncMock(return_value=plugin)
        resp = await client.get("/api/alerts/channels")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["plugin_module_name"] == "email"


class TestGetChannel:
    async def test_not_found(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.get(f"/api/alerts/channels/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateChannel:
    async def test_not_found(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.patch(f"/api/alerts/channels/{uuid.uuid4()}", json={"name": "X"})
        assert resp.status_code == 404

    async def test_rename(self, client, mock_db):
        ch = _channel()
        plugin = _integration_plugin(ch.plugin_id)
        # Two get() calls inside the route: load channel, then re-load plugin in _to_read.
        mock_db.get = AsyncMock(side_effect=[ch, plugin])
        resp = await client.patch(f"/api/alerts/channels/{ch.id}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert ch.name == "renamed"


class TestDeleteChannel:
    async def test_not_found(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.delete(f"/api/alerts/channels/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_deletes(self, client, mock_db):
        ch = _channel()
        mock_db.get = AsyncMock(return_value=ch)
        resp = await client.delete(f"/api/alerts/channels/{ch.id}")
        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(ch)
