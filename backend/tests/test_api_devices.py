"""Unit tests for device API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.devices import _compute_online, router
from tests.conftest import DEVICE_ID, PLUGIN_ID, SENSOR_ID, make_execute_result, make_mock_db

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


def _make_device(is_active=True, last_seen=None):
    d = MagicMock()
    d.id = DEVICE_ID
    d.plugin_id = PLUGIN_ID
    d.external_id = "dev-001"
    d.name = "Test Device"
    d.location = "Lab"
    d.last_seen = last_seen
    d.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    d.sensors = []
    d.plugin = MagicMock()
    d.plugin.is_active = is_active
    return d


def _make_sensor():
    s = MagicMock()
    s.id = SENSOR_ID
    s.device_id = DEVICE_ID
    s.key = "temperature"
    s.name = "Temperature"
    s.unit = "°C"
    s.value_type = "numeric"
    s.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    return s


# ── _compute_online unit tests ───────────────────────────────────

def _online_device(is_active, last_seen):
    d = MagicMock()
    d.plugin = MagicMock()
    d.plugin.is_active = is_active
    d.last_seen = last_seen
    return d


@pytest.mark.parametrize("is_active,last_seen,expected", [
    (False, datetime.now(UTC),                    False),  # plugin inactive
    (True,  None,                                 False),  # never seen
    (True,  datetime.now(UTC),                    True),   # recently seen
    (True,  datetime(2020, 1, 1, tzinfo=UTC),     False),  # stale
])
def test_compute_online(is_active, last_seen, expected):
    assert _compute_online(_online_device(is_active, last_seen)) is expected


# ── list_devices ──────────────────────────────────────────────────

class TestListDevices:
    async def test_empty_list_returns_200(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))

        resp = await client.get("/api/devices")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_all_devices(self, client, mock_db):
        device = _make_device()
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[device]))

        resp = await client.get("/api/devices")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_filter_by_is_online_accepted(self, client, mock_db):
        # SQL WHERE clause handles filtering; mock returns empty (DB filtered)
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))

        resp = await client.get("/api/devices?is_online=true")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_filter_by_is_online_false_accepted(self, client, mock_db):
        device = _make_device(is_active=True, last_seen=datetime(2020, 1, 1, tzinfo=UTC))
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[device]))

        resp = await client.get("/api/devices?is_online=false")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── get_device ────────────────────────────────────────────────────

class TestGetDevice:
    async def test_found_returns_device_detail(self, client, mock_db):
        device = _make_device()
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=device))

        resp = await client.get(f"/api/devices/{DEVICE_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Test Device"
        assert body["sensors"] == []

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=None))

        resp = await client.get(f"/api/devices/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── list_device_sensors ───────────────────────────────────────────

class TestListDeviceSensors:
    async def test_device_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.get(f"/api/devices/{uuid.uuid4()}/sensors")
        assert resp.status_code == 404

    async def test_returns_sensors_for_device(self, client, mock_db):
        sensor = _make_sensor()
        mock_db.get = AsyncMock(return_value=MagicMock())  # device found
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[sensor]))

        resp = await client.get(f"/api/devices/{DEVICE_ID}/sensors")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["key"] == "temperature"
