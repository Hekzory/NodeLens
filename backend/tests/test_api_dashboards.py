"""Unit tests for dashboard API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.dashboards import router
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


class TestCreateDashboard:
    async def test_create_non_default_dashboard_returns_201(self, client, mock_db):
        resp = await client.post("/api/dashboards", json={"name": "My Dashboard", "is_default": False})
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Dashboard"
        assert resp.json()["is_default"] is False

    async def test_creating_default_dashboard_unsets_existing_default(self, client, mock_db):
        existing_default = MagicMock()
        existing_default.is_default = True

        # _unset_default_dashboards runs select(...).scalars().all() → [existing_default]
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[existing_default]))

        resp = await client.post("/api/dashboards", json={"name": "New Default", "is_default": True})
        assert resp.status_code == 201
        # Existing default should have been cleared
        assert existing_default.is_default is False

    async def test_creating_non_default_does_not_touch_existing_defaults(self, client, mock_db):
        existing_default = MagicMock()
        existing_default.is_default = True

        # execute should NOT be called for _unset_default_dashboards when is_default=False
        execute_mock = AsyncMock(return_value=make_execute_result(scalars_all=[existing_default]))
        mock_db.execute = execute_mock

        resp = await client.post("/api/dashboards", json={"name": "Normal Dashboard", "is_default": False})
        assert resp.status_code == 201
        # is_default on existing should remain untouched
        assert existing_default.is_default is True


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
