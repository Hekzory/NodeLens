"""Unit tests for alert rule creation validation and acknowledgment logic."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.alerts import router
from tests.conftest import SENSOR_ID, make_mock_db

# Minimal test app — no lifespan, no DB init
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


# ── Alert rule creation validation ───────────────────────────────

_BASE_RULE = {
    "name": "Test Rule",
    "sensor_id": str(SENSOR_ID),
    "rule_type": "instant",
    "condition": "gt",
    "threshold": 25.0,
}


class TestCreateAlertRuleValidation:
    async def test_sensor_not_found_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)  # sensor not found
        resp = await client.post("/api/alerts/rules", json=_BASE_RULE)
        assert resp.status_code == 400
        assert "Sensor" in resp.json()["detail"]

    async def test_aggregated_rule_without_aggregation_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())  # sensor found
        payload = {**_BASE_RULE, "rule_type": "aggregated", "duration_seconds": 60}
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 400
        assert "aggregation" in resp.json()["detail"].lower()

    async def test_aggregated_rule_with_zero_duration_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())
        payload = {**_BASE_RULE, "rule_type": "aggregated", "aggregation": "avg", "duration_seconds": 0}
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 400
        assert "duration_seconds" in resp.json()["detail"].lower()

    async def test_non_nodata_condition_without_threshold_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())
        payload = {k: v for k, v in _BASE_RULE.items() if k != "threshold"}
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 400
        assert "threshold" in resp.json()["detail"].lower()

    async def test_nodata_condition_without_threshold_is_accepted(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())
        payload = {
            "name": "No Data Rule",
            "sensor_id": str(SENSOR_ID),
            "rule_type": "instant",
            "condition": "no_data",
            # no threshold
        }
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 201

    async def test_valid_instant_rule_returns_201(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())
        resp = await client.post("/api/alerts/rules", json=_BASE_RULE)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Test Rule"
        assert body["condition"] == "gt"
        assert body["threshold"] == 25.0

    async def test_valid_aggregated_rule_returns_201(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=MagicMock())
        payload = {
            **_BASE_RULE,
            "name": "Agg Rule",
            "rule_type": "aggregated",
            "aggregation": "avg",
            "duration_seconds": 300,
        }
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 201


# ── Alert acknowledgment ─────────────────────────────────────────

class TestAcknowledgeAlert:
    async def test_missing_history_record_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.post(f"/api/alerts/history/{uuid.uuid4()}/acknowledge")
        assert resp.status_code == 404

    async def test_already_acknowledged_alert_returns_400(self, client, mock_db):
        mock_history = MagicMock()
        mock_history.acknowledged_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        async def get_side(model, pk):
            return mock_history

        mock_db.get = AsyncMock(side_effect=get_side)
        resp = await client.post(f"/api/alerts/history/{uuid.uuid4()}/acknowledge")
        assert resp.status_code == 400
        assert "acknowledged" in resp.json()["detail"].lower()

    async def test_unacknowledged_alert_is_acknowledged_successfully(self, client, mock_db):
        history_id = uuid.uuid4()
        rule_id = uuid.uuid4()

        mock_history = MagicMock()
        mock_history.id = history_id
        mock_history.rule_id = rule_id
        mock_history.acknowledged_at = None
        mock_history.triggered_value = 42.0
        mock_history.message = "Threshold exceeded"
        mock_history.triggered_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_history.rule_name = None  # Pydantic reads this via model_validate(history)

        mock_rule = MagicMock()
        mock_rule.name = "My Rule"

        async def get_side(model, pk):
            from nodelens.db.models.alert import AlertHistory, AlertRule
            if model is AlertHistory:
                return mock_history
            if model is AlertRule:
                return mock_rule
            return None

        mock_db.get = AsyncMock(side_effect=get_side)

        resp = await client.post(f"/api/alerts/history/{history_id}/acknowledge")
        assert resp.status_code == 200
        # The endpoint sets acknowledged_at on the history object
        assert mock_history.acknowledged_at is not None
