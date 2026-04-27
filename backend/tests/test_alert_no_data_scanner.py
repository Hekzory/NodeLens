"""Unit tests for the no_data alert scanner."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from nodelens.workers.alerts import liveness, no_data_scanner


def _make_rule(**kwargs):
    rule = MagicMock()
    rule.id = kwargs.get("id", uuid.uuid4())
    rule.name = kwargs.get("name", "silence-alarm")
    rule.sensor_id = kwargs.get("sensor_id", uuid.uuid4())
    rule.condition = "no_data"
    rule.duration_seconds = kwargs.get("duration_seconds", 60)
    rule.cooldown_seconds = kwargs.get("cooldown_seconds", 300)
    rule.is_active = kwargs.get("is_active", True)
    return rule


def _scalars_all(items):
    """Build a mock for `session.execute()` returning .scalars().all() == items."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(items)
    return result


def _rows_all(rows):
    """Build a mock for `session.execute()` returning .all() == rows."""
    result = MagicMock()
    result.all.return_value = list(rows)
    return result


@pytest.fixture(autouse=True)
def _reset_liveness():
    liveness.reset_for_tests()
    yield
    liveness.reset_for_tests()


@pytest.fixture
def healthy_pipeline():
    """Default: scanner has been up >1h, engine processed an event 1s ago."""
    now = datetime.now(UTC)
    liveness.mark_scanner_started(now - timedelta(hours=1))
    liveness.mark_event_processed(now - timedelta(seconds=1))
    return now


@pytest.fixture
def patched_helpers(monkeypatch):
    """Patch is_in_cooldown and dispatch_fires; return the mocks for assertions."""
    cooldown_mock = AsyncMock(return_value=False)
    dispatch_mock = AsyncMock()
    monkeypatch.setattr(no_data_scanner, "is_in_cooldown", cooldown_mock)
    monkeypatch.setattr(no_data_scanner, "dispatch_fires", dispatch_mock)
    return cooldown_mock, dispatch_mock


class TestLastSeenForSensors:
    async def test_empty_input_returns_empty_dict_without_query(self):
        session = MagicMock()
        session.execute = AsyncMock()
        out = await no_data_scanner._last_seen_for_sensors(session, set())
        assert out == {}
        session.execute.assert_not_called()

    async def test_missing_sensors_default_to_none(self):
        sid_a = uuid.uuid4()
        sid_b = uuid.uuid4()
        ts = datetime.now(UTC)
        session = AsyncMock()
        # Only sid_a has telemetry; sid_b is silent.
        session.execute = AsyncMock(return_value=_rows_all([(sid_a, ts)]))

        out = await no_data_scanner._last_seen_for_sensors(session, {sid_a, sid_b})
        assert out[sid_a] == ts
        assert out[sid_b] is None


class TestScanOnce:
    async def test_fires_when_silence_exceeds_window(self, healthy_pipeline, patched_helpers):
        cooldown_mock, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rule = _make_rule(duration_seconds=60)

        last_seen = now - timedelta(seconds=200)
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        r = AsyncMock()

        await no_data_scanner._scan_once(session, r, now)

        dispatch_mock.assert_awaited_once()
        decisions = dispatch_mock.await_args.args[2]
        assert len(decisions) == 1
        decision = decisions[0]
        assert decision.rule is rule
        assert decision.triggered_value == 200.0
        assert "no data for 200s" in decision.message
        assert "threshold 60s" in decision.message
        cooldown_mock.assert_awaited_once()

    async def test_does_not_fire_when_within_window(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rule = _make_rule(duration_seconds=60)
        last_seen = now - timedelta(seconds=30)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        dispatch_mock.assert_not_awaited()

    async def test_does_not_fire_when_in_cooldown(self, healthy_pipeline, patched_helpers):
        cooldown_mock, dispatch_mock = patched_helpers
        cooldown_mock.return_value = True
        now = healthy_pipeline
        rule = _make_rule(duration_seconds=60)
        last_seen = now - timedelta(seconds=200)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        cooldown_mock.assert_awaited_once()
        dispatch_mock.assert_not_awaited()

    async def test_no_active_rules_short_circuits(self, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = datetime.now(UTC)
        liveness.mark_scanner_started(now - timedelta(hours=1))
        liveness.mark_event_processed(now - timedelta(seconds=1))

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalars_all([]))
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        # Only the rule-loading query runs; no telemetry query, no dispatch.
        assert session.execute.await_count == 1
        dispatch_mock.assert_not_awaited()

    async def test_skips_rules_with_zero_duration(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rule = _make_rule(duration_seconds=0)

        session = AsyncMock()
        # Only the rule-loading query is consumed; the sensor query never runs
        # because the defensive guard skips before sensor_ids is populated.
        # However the implementation still runs the sensor query for the set of
        # candidate sensor_ids, so prepare a side_effect for both.
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, now - timedelta(seconds=1000))]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        dispatch_mock.assert_not_awaited()

    async def test_skips_when_last_seen_is_none(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rule = _make_rule(duration_seconds=60)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([]),  # sensor never reported
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        dispatch_mock.assert_not_awaited()

    async def test_skips_during_scanner_startup_grace(self, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = datetime.now(UTC)
        # Scanner just started 5s ago; rule has 60s window.
        liveness.mark_scanner_started(now - timedelta(seconds=5))
        liveness.mark_event_processed(now - timedelta(seconds=1))

        rule = _make_rule(duration_seconds=60)
        last_seen = now - timedelta(hours=1)  # ancient silence

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)
        dispatch_mock.assert_not_awaited()

        # Now advance past the grace window: scanner-uptime > duration.
        liveness.reset_for_tests()
        liveness.mark_scanner_started(now - timedelta(seconds=120))
        liveness.mark_event_processed(now - timedelta(seconds=1))

        session2 = AsyncMock()
        session2.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session2, AsyncMock(), now)
        dispatch_mock.assert_awaited_once()

    async def test_skips_when_engine_has_no_recent_events(self, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = datetime.now(UTC)
        # Scanner up long enough; engine has not processed anything recently.
        liveness.mark_scanner_started(now - timedelta(hours=1))
        # _last_event_processed_at remains None → pipeline-liveness guard kicks in.

        rule = _make_rule(duration_seconds=60)
        last_seen = now - timedelta(seconds=300)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)
        dispatch_mock.assert_not_awaited()

        # Mark a fresh engine event and re-scan → fires.
        liveness.mark_event_processed(now - timedelta(seconds=1))
        session2 = AsyncMock()
        session2.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session2, AsyncMock(), now)
        dispatch_mock.assert_awaited_once()

    async def test_groups_queries_by_sensor(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        sensor_id = uuid.uuid4()
        rule_a = _make_rule(sensor_id=sensor_id, duration_seconds=60)
        rule_b = _make_rule(sensor_id=sensor_id, duration_seconds=60, name="rule-b")

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule_a, rule_b]),
            _rows_all([(sensor_id, now - timedelta(seconds=200))]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        # Two execute() calls only: rules + grouped sensor query.
        assert session.execute.await_count == 2
        # Both rules fire → one dispatch with two decisions.
        dispatch_mock.assert_awaited_once()
        decisions = dispatch_mock.await_args.args[2]
        assert len(decisions) == 2

    async def test_batches_fires_into_one_dispatch_call(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rules = [_make_rule(name=f"rule-{i}", duration_seconds=60) for i in range(3)]
        rows = [(rule.sensor_id, now - timedelta(seconds=120 + i)) for i, rule in enumerate(rules)]

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all(rules),
            _rows_all(rows),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        dispatch_mock.assert_awaited_once()
        decisions = dispatch_mock.await_args.args[2]
        assert len(decisions) == 3

    async def test_fire_message_includes_elapsed_and_threshold(self, healthy_pipeline, patched_helpers):
        _, dispatch_mock = patched_helpers
        now = healthy_pipeline
        rule = _make_rule(name="kitchen-temp", duration_seconds=60)
        last_seen = now - timedelta(seconds=137)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            _scalars_all([rule]),
            _rows_all([(rule.sensor_id, last_seen)]),
        ])
        await no_data_scanner._scan_once(session, AsyncMock(), now)

        decisions = dispatch_mock.await_args.args[2]
        msg = decisions[0].message
        assert "kitchen-temp" in msg
        assert "no data for 137s" in msg
        assert "threshold 60s" in msg
        assert "last seen" in msg
        assert decisions[0].triggered_value == 137.0
