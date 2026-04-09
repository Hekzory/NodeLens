"""Unit tests for alert rule creation validation and acknowledgment logic."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from nodelens.api.deps import get_db
from nodelens.api.routes.alerts import router
from tests.conftest import SENSOR_ID, make_execute_result, make_mock_db

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


# ── Helpers ──────────────────────────────────────────────────────

_BASE_RULE = {
    "name": "Test Rule",
    "sensor_id": str(SENSOR_ID),
    "rule_type": "instant",
    "condition": "gt",
    "threshold": 25.0,
}


def _make_rule():
    r = MagicMock()
    r.id = uuid.uuid4()
    r.name = "Test Rule"
    r.description = None
    r.sensor_id = SENSOR_ID
    r.rule_type = "instant"
    r.condition = "gt"
    r.threshold = 25.0
    r.aggregation = None
    r.duration_seconds = 0
    r.cooldown_seconds = 300
    r.severity = "warning"
    r.is_active = True
    r.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    r.updated_at = datetime(2024, 1, 1, tzinfo=UTC)
    return r


def _make_history():
    h = MagicMock()
    h.id = uuid.uuid4()
    h.rule_id = uuid.uuid4()
    h.rule_name = None
    h.triggered_value = 42.0
    h.message = "Threshold exceeded"
    h.triggered_at = datetime(2024, 1, 1, tzinfo=UTC)
    h.acknowledged_at = None
    return h


# ── Alert rule creation validation ───────────────────────────────

class TestCreateAlertRuleValidation:
    async def test_sensor_not_found_returns_400(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)  # sensor not found
        resp = await client.post("/api/alerts/rules", json=_BASE_RULE)
        assert resp.status_code == 400
        assert "Sensor" in resp.json()["detail"]

    @pytest.mark.parametrize("payload,keyword", [
        ({**_BASE_RULE, "rule_type": "aggregated", "duration_seconds": 60},                           "aggregation"),
        ({**_BASE_RULE, "rule_type": "aggregated", "aggregation": "avg", "duration_seconds": 0},      "duration_seconds"),
        ({k: v for k, v in _BASE_RULE.items() if k != "threshold"},                                   "threshold"),
    ])
    async def test_invalid_rule_body_returns_400(self, client, mock_db, payload, keyword):
        mock_db.get = AsyncMock(return_value=MagicMock())  # sensor found
        resp = await client.post("/api/alerts/rules", json=payload)
        assert resp.status_code == 400
        assert keyword in resp.json()["detail"].lower()

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
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=None))
        resp = await client.post(f"/api/alerts/history/{uuid.uuid4()}/acknowledge")
        assert resp.status_code == 404

    async def test_already_acknowledged_alert_returns_400(self, client, mock_db):
        mock_history = MagicMock()
        mock_history.acknowledged_at = datetime(2024, 1, 1, tzinfo=UTC)

        mock_db.execute = AsyncMock(
            return_value=make_execute_result(scalar_one_or_none=mock_history)
        )
        resp = await client.post(f"/api/alerts/history/{uuid.uuid4()}/acknowledge")
        assert resp.status_code == 400
        assert "acknowledged" in resp.json()["detail"].lower()

    async def test_unacknowledged_alert_is_acknowledged_successfully(self, client, mock_db):
        history_id = uuid.uuid4()
        rule_id = uuid.uuid4()

        mock_rule = MagicMock()
        mock_rule.id = rule_id
        mock_rule.name = "My Rule"

        mock_history = MagicMock()
        mock_history.id = history_id
        mock_history.rule_id = rule_id
        mock_history.acknowledged_at = None
        mock_history.triggered_value = 42.0
        mock_history.message = "Threshold exceeded"
        mock_history.triggered_at = datetime(2024, 1, 1, tzinfo=UTC)
        mock_history.rule_name = None
        mock_history.rule = mock_rule

        mock_db.execute = AsyncMock(
            return_value=make_execute_result(scalar_one_or_none=mock_history)
        )

        resp = await client.post(f"/api/alerts/history/{history_id}/acknowledge")
        assert resp.status_code == 200
        # The endpoint sets acknowledged_at on the history object
        assert mock_history.acknowledged_at is not None


# ── List alert rules ──────────────────────────────────────────────

class TestListAlertRules:
    async def test_empty_list_returns_200(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/alerts/rules")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_rules(self, client, mock_db):
        rule = _make_rule()
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[rule]))
        resp = await client.get("/api/alerts/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Test Rule"

    async def test_filter_by_is_active_accepted(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/alerts/rules?is_active=true")
        assert resp.status_code == 200


# ── Get alert rule ────────────────────────────────────────────────

class TestGetAlertRule:
    async def test_found_returns_rule(self, client, mock_db):
        rule = _make_rule()
        mock_db.get = AsyncMock(return_value=rule)
        resp = await client.get(f"/api/alerts/rules/{rule.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Rule"

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.get(f"/api/alerts/rules/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── Update alert rule ─────────────────────────────────────────────

class TestUpdateAlertRule:
    async def test_update_name_returns_200(self, client, mock_db):
        rule = _make_rule()
        mock_db.get = AsyncMock(return_value=rule)
        resp = await client.patch(f"/api/alerts/rules/{rule.id}", json={"name": "Updated"})
        assert resp.status_code == 200
        assert rule.name == "Updated"

    async def test_update_with_missing_sensor_returns_400(self, client, mock_db):
        rule = _make_rule()
        # First get: returns rule; second get: sensor not found
        mock_db.get = AsyncMock(side_effect=[rule, None])
        resp = await client.patch(
            f"/api/alerts/rules/{rule.id}",
            json={"sensor_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 400

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.patch(f"/api/alerts/rules/{uuid.uuid4()}", json={"name": "X"})
        assert resp.status_code == 404


# ── Delete alert rule ─────────────────────────────────────────────

class TestDeleteAlertRule:
    async def test_found_deletes_and_returns_204(self, client, mock_db):
        rule = _make_rule()
        mock_db.get = AsyncMock(return_value=rule)
        resp = await client.delete(f"/api/alerts/rules/{rule.id}")
        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(rule)

    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)
        resp = await client.delete(f"/api/alerts/rules/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── List alert history ────────────────────────────────────────────

class TestListAlertHistory:
    async def test_empty_history_returns_200(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/alerts/history")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_history_includes_rule_name(self, client, mock_db):
        history = _make_history()
        mock_rule = MagicMock()
        mock_rule.name = "My Rule"
        history.rule = mock_rule

        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[history]))

        resp = await client.get("/api/alerts/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["rule_name"] == "My Rule"
        assert body[0]["message"] == "Threshold exceeded"

    async def test_filter_params_accepted(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))
        resp = await client.get("/api/alerts/history?acknowledged=false&limit=10&offset=0")
        assert resp.status_code == 200
