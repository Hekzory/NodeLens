"""Unit tests for telemetry API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.telemetry import router
from tests.conftest import SENSOR_ID, make_execute_result, make_mock_db

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


def _mock_sensor(sensor_id=SENSOR_ID, key="temperature", name="Temperature"):
    s = MagicMock()
    s.id = sensor_id
    s.key = key
    s.name = name
    return s


class TestGetTelemetrySeries:
    async def test_unknown_sensor_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.get(f"/api/telemetry/{SENSOR_ID}")
        assert resp.status_code == 404

    async def test_sensor_with_no_data_returns_empty_series(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=_mock_sensor())
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))

        resp = await client.get(f"/api/telemetry/{SENSOR_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["points"] == []
        assert body["sensor_id"] == str(SENSOR_ID)

    async def test_points_returned_in_chronological_order(self, client, mock_db):
        """Endpoint reverses DESC query results so earliest point is first."""
        ts1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        ts2 = datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)

        record_new = MagicMock()
        record_new.time = ts2
        record_new.sensor_id = SENSOR_ID
        record_new.value_numeric = 30.0
        record_new.value_text = None

        record_old = MagicMock()
        record_old.time = ts1
        record_old.sensor_id = SENSOR_ID
        record_old.value_numeric = 20.0
        record_old.value_text = None

        # DB returns newest first (DESC), endpoint reverses them
        mock_db.get = AsyncMock(return_value=_mock_sensor())
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[record_new, record_old]))

        resp = await client.get(f"/api/telemetry/{SENSOR_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        # After reversal, oldest should be first
        assert body["points"][0]["value_numeric"] == 20.0
        assert body["points"][1]["value_numeric"] == 30.0


class TestGetTelemetryLatest:
    async def test_unknown_sensor_returns_404(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=None))
        resp = await client.get(f"/api/telemetry/{SENSOR_ID}/latest")
        assert resp.status_code == 404

    async def test_sensor_with_no_records_returns_null_values(self, client, mock_db):
        sensor = _mock_sensor()
        # First execute: find sensor; second execute: find latest record
        mock_db.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_one_or_none=sensor),
            make_execute_result(scalar_one_or_none=None),
        ])

        resp = await client.get(f"/api/telemetry/{SENSOR_ID}/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["value_numeric"] is None
        assert body["value_text"] is None
        assert body["time"] is None
        assert body["sensor_key"] == "temperature"

    async def test_latest_record_values_are_returned(self, client, mock_db):
        sensor = _mock_sensor()
        record = MagicMock()
        record.value_numeric = 22.5
        record.value_text = None
        record.time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_db.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_one_or_none=sensor),
            make_execute_result(scalar_one_or_none=record),
        ])

        resp = await client.get(f"/api/telemetry/{SENSOR_ID}/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["value_numeric"] == 22.5
