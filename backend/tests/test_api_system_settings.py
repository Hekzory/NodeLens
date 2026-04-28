"""Unit tests for the system settings API."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.system_settings import router
from nodelens.system_settings import REGISTRY, runtime_settings
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


def _row(key: str, value, when: datetime | None = None) -> MagicMock:
    r = MagicMock()
    r.key = key
    r.value = value
    r.updated_at = when or datetime(2026, 1, 1, tzinfo=UTC)
    return r


class TestListSettings:
    async def test_returns_full_registry_with_defaults(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))

        resp = await client.get("/api/system/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert {entry["key"] for entry in body} == set(REGISTRY.keys())
        for entry in body:
            assert entry["is_default"] is True
            assert entry["value"] == REGISTRY[entry["key"]].default
            assert entry["updated_at"] is None

    async def test_marks_overridden_keys_with_is_default_false(self, client, mock_db):
        # DB has an override for disk_budget_gb; cache should reflect it.
        mock_db.execute = AsyncMock(
            return_value=make_execute_result(scalars_all=[_row("disk_budget_gb", 7)])
        )
        runtime_settings._cache["disk_budget_gb"] = 7

        resp = await client.get("/api/system/settings")
        body = resp.json()
        entry = next(e for e in body if e["key"] == "disk_budget_gb")
        assert entry["value"] == 7
        assert entry["is_default"] is False
        assert entry["updated_at"] is not None


class TestGetSetting:
    async def test_unknown_key_returns_404(self, client, mock_db):
        resp = await client.get("/api/system/settings/does_not_exist")
        assert resp.status_code == 404

    async def test_known_key_returns_metadata(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/system/settings/retention_days")
        assert resp.status_code == 200
        body = resp.json()
        assert body["key"] == "retention_days"
        assert body["requires_restart"] is True
        assert body["unit"] == "days"


class TestPatchSettings:
    async def test_empty_body_returns_422(self, client, mock_db):
        resp = await client.patch("/api/system/settings", json={"updates": {}})
        assert resp.status_code == 422

    async def test_unknown_key_returns_422_with_field_errors(self, client, mock_db):
        resp = await client.patch(
            "/api/system/settings", json={"updates": {"made_up": 1}}
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "made_up" in body["detail"]["field_errors"]

    async def test_out_of_range_returns_422(self, client, mock_db):
        resp = await client.patch(
            "/api/system/settings", json={"updates": {"retention_days": 0}}
        )
        assert resp.status_code == 422
        assert "retention_days" in resp.json()["detail"]["field_errors"]

    async def test_cross_field_invariant_returns_422(self, client, mock_db):
        # retention=5 with compression default of 7 is invalid.
        resp = await client.patch(
            "/api/system/settings", json={"updates": {"retention_days": 5}}
        )
        assert resp.status_code == 422
        assert "error" in resp.json()["detail"]

    async def test_happy_path_persists_and_flags_restart(self, client, mock_db):
        # After update, list query returns the new row + cache reflects new value.
        mock_db.execute = AsyncMock(
            return_value=make_execute_result(scalars_all=[_row("retention_days", 90)])
        )

        resp = await client.patch(
            "/api/system/settings", json={"updates": {"retention_days": 90}}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "retention_days" in body["requires_restart_keys"]
        assert body["updated"][0]["key"] == "retention_days"
        assert body["updated"][0]["value"] == 90
        assert body["updated"][0]["is_default"] is False

    async def test_live_setting_not_in_requires_restart_keys(self, client, mock_db):
        mock_db.execute = AsyncMock(
            return_value=make_execute_result(scalars_all=[_row("disk_budget_gb", 12)])
        )
        resp = await client.patch(
            "/api/system/settings", json={"updates": {"disk_budget_gb": 12}}
        )
        assert resp.status_code == 200
        assert resp.json()["requires_restart_keys"] == []


class TestDeleteSetting:
    async def test_unknown_key_returns_404(self, client, mock_db):
        resp = await client.delete("/api/system/settings/bogus")
        assert resp.status_code == 404

    async def test_known_key_deletes_and_returns_204(self, client, mock_db):
        resp = await client.delete("/api/system/settings/retention_days")
        assert resp.status_code == 204
        # The route should issue a DELETE statement against the session.
        assert mock_db.execute.await_count >= 1
