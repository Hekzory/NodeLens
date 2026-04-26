"""Unit tests for the alert dispatcher."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from nodelens.workers.alerts.dispatcher import dispatch_fires
from nodelens.workers.alerts.evaluator import FireDecision


def _session_mock() -> AsyncMock:
    """AsyncMock with .add as sync MagicMock (matches SQLAlchemy AsyncSession)."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _rule():
    rule = MagicMock()
    rule.id = uuid.uuid4()
    rule.name = "Hot sensor"
    rule.sensor_id = uuid.uuid4()
    return rule


def _decision(rule):
    return FireDecision(
        rule=rule,
        triggered_value=42.0,
        message="rule fired",
        triggered_at=datetime.now(UTC),
    )


def _channel(name="ops-email", plugin_id=None):
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.name = name
    ch.plugin_id = plugin_id or uuid.uuid4()
    ch.config = {"to": "ops@example.com"}
    return ch


def _plugin(pid):
    p = MagicMock()
    p.id = pid
    p.module_name = "email"
    return p


class TestDispatchFires:
    async def test_no_fires_no_op(self):
        session = _session_mock()
        r = AsyncMock()
        await dispatch_fires(session, r, [])
        session.add.assert_not_called()
        r.xadd.assert_not_called()

    async def test_no_active_channels_writes_history_only(self):
        session = _session_mock()
        rule = _rule()
        # Device-name lookup → return name; channels lookup → empty list.
        device_result = MagicMock()
        device_result.scalar.return_value = "thermostat"
        channels_result = MagicMock()
        channels_result.all.return_value = []
        session.execute = AsyncMock(side_effect=[device_result, channels_result])

        r = AsyncMock()
        await dispatch_fires(session, r, [_decision(rule)])

        # AlertHistory row added.
        assert session.add.call_count == 1
        # Nothing dispatched.
        r.xadd.assert_not_called()
        session.commit.assert_awaited_once()

    async def test_dispatches_one_event_per_channel(self):
        session = _session_mock()
        rule = _rule()

        plugin_id = uuid.uuid4()
        ch1 = _channel("ops", plugin_id)
        ch2 = _channel("homeowner", plugin_id)
        plugin = _plugin(plugin_id)

        device_result = MagicMock()
        device_result.scalar.return_value = "thermostat"
        channels_result = MagicMock()
        channels_result.all.return_value = [(ch1, plugin), (ch2, plugin)]
        session.execute = AsyncMock(side_effect=[device_result, channels_result])

        r = AsyncMock()
        await dispatch_fires(session, r, [_decision(rule)])

        # One history row, two dispatch events.
        assert session.add.call_count == 1
        assert r.xadd.await_count == 2

        # Verify the dispatch payload shape.
        first_call_args = r.xadd.await_args_list[0]
        stream = first_call_args.args[0]
        fields = first_call_args.args[1]
        assert stream == "alert_dispatch_events"
        assert fields["plugin_id"] == str(plugin_id)
        assert "channel_id" in fields
        body = json.loads(fields["alert_message_json"])
        assert body["rule_name"] == "Hot sensor"
        assert body["device_name"] == "thermostat"
        assert body["triggered_value"] == 42.0
