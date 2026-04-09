"""Unit tests for dashboard API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.dashboards import router
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


class TestCreateDashboard:
    async def test_create_non_default_dashboard_returns_201(self, client, mock_db):
        resp = await client.post("/api/dashboards", json={"name": "My Dashboard", "is_default": False})
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Dashboard"
        assert resp.json()["is_default"] is False

    async def test_creating_default_dashboard_unsets_existing_default(self, client, mock_db):
        resp = await client.post("/api/dashboards", json={"name": "New Default", "is_default": True})
        assert resp.status_code == 201
        # _unset_default_dashboards now issues a bulk UPDATE via execute
        mock_db.execute.assert_called()

    async def test_creating_non_default_does_not_touch_existing_defaults(self, client, mock_db):
        # execute should NOT be called for _unset_default_dashboards when is_default=False
        mock_db.execute = AsyncMock(return_value=make_execute_result())

        resp = await client.post("/api/dashboards", json={"name": "Normal Dashboard", "is_default": False})
        assert resp.status_code == 201
        mock_db.execute.assert_not_called()


class TestWidgetOwnershipValidation:
    async def test_delete_widget_belonging_to_different_dashboard_returns_404(self, client, mock_db):
        dashboard_id = uuid.uuid4()
        other_dashboard_id = uuid.uuid4()
        widget_id = uuid.uuid4()

        # Widget exists but belongs to a DIFFERENT dashboard
        mock_widget = MagicMock()
        mock_widget.id = widget_id
        mock_widget.dashboard_id = other_dashboard_id  # not the one in the URL

        mock_db.get = AsyncMock(return_value=mock_widget)

        resp = await client.delete(f"/api/dashboards/{dashboard_id}/widgets/{widget_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_widget_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.delete(f"/api/dashboards/{uuid.uuid4()}/widgets/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_widget_belonging_to_correct_dashboard_succeeds(self, client, mock_db):
        dashboard_id = uuid.uuid4()
        widget_id = uuid.uuid4()

        mock_widget = MagicMock()
        mock_widget.id = widget_id
        mock_widget.dashboard_id = dashboard_id  # correct ownership
        mock_widget.widget_type = "chart"
        mock_widget.title = "Old Title"
        mock_widget.sensor_id = None
        mock_widget.config = {}
        mock_widget.layout = {}
        mock_widget.sort_order = 0

        mock_db.get = AsyncMock(return_value=mock_widget)

        resp = await client.patch(
            f"/api/dashboards/{dashboard_id}/widgets/{widget_id}",
            json={"title": "New Title"},
        )
        assert resp.status_code == 200
        # The title should have been set on the widget object
        assert mock_widget.title == "New Title"


# ── Helpers ──────────────────────────────────────────────────────

def _make_dashboard():
    d = MagicMock()
    d.id = uuid.uuid4()
    d.name = "My Dashboard"
    d.description = None
    d.is_default = False
    d.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    d.updated_at = datetime(2024, 1, 1, tzinfo=UTC)
    return d


# ── List dashboards ───────────────────────────────────────────────

class TestListDashboards:
    async def test_empty_returns_200(self, client, mock_db):
        result = make_execute_result()
        result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/dashboards")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_dashboards_with_widget_count(self, client, mock_db):
        dashboard = _make_dashboard()
        result = make_execute_result()
        result.all.return_value = [(dashboard, 5)]
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.get("/api/dashboards")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "My Dashboard"
        assert body[0]["widget_count"] == 5


# ── Get dashboard ─────────────────────────────────────────────────

class TestGetDashboard:
    async def test_found_returns_detail(self, client, mock_db):
        dashboard = _make_dashboard()
        dashboard.widgets = []
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=dashboard))

        resp = await client.get(f"/api/dashboards/{dashboard.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "My Dashboard"
        assert body["widgets"] == []

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=None))

        resp = await client.get(f"/api/dashboards/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── Update dashboard ──────────────────────────────────────────────

class TestUpdateDashboard:
    async def test_update_name_returns_200(self, client, mock_db):
        dashboard = _make_dashboard()
        mock_db.get = AsyncMock(return_value=dashboard)
        # execute for widget count query
        result = make_execute_result()
        result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.patch(f"/api/dashboards/{dashboard.id}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert dashboard.name == "Renamed"

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.patch(f"/api/dashboards/{uuid.uuid4()}", json={"name": "X"})
        assert resp.status_code == 404


# ── Delete dashboard ──────────────────────────────────────────────

class TestDeleteDashboard:
    async def test_found_deletes_and_returns_204(self, client, mock_db):
        dashboard = _make_dashboard()
        mock_db.get = AsyncMock(return_value=dashboard)

        resp = await client.delete(f"/api/dashboards/{dashboard.id}")
        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(dashboard)

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.delete(f"/api/dashboards/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── Create widget ─────────────────────────────────────────────────

class TestCreateWidget:
    _WIDGET_PAYLOAD = {
        "widget_type": "chart",
        "title": "Temp Chart",
        "config": {},
        "layout": {},
        "sort_order": 0,
    }

    async def test_dashboard_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.post(
            f"/api/dashboards/{uuid.uuid4()}/widgets",
            json=self._WIDGET_PAYLOAD,
        )
        assert resp.status_code == 404

    async def test_sensor_not_found_returns_400(self, client, mock_db):
        dashboard = _make_dashboard()
        # First get: dashboard found; second get: sensor not found
        mock_db.get = AsyncMock(side_effect=[dashboard, None])

        payload = {**self._WIDGET_PAYLOAD, "sensor_id": str(SENSOR_ID)}
        resp = await client.post(
            f"/api/dashboards/{dashboard.id}/widgets",
            json=payload,
        )
        assert resp.status_code == 400

    async def test_valid_widget_returns_201(self, client, mock_db):
        dashboard = _make_dashboard()
        mock_db.get = AsyncMock(return_value=dashboard)

        resp = await client.post(
            f"/api/dashboards/{dashboard.id}/widgets",
            json=self._WIDGET_PAYLOAD,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["widget_type"] == "chart"
        assert body["title"] == "Temp Chart"
