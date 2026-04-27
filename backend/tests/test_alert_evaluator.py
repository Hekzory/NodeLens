"""Unit tests for the alert rule evaluator."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from nodelens.schemas.events import TelemetryEvent
from nodelens.workers.alerts.conditions.base import compare
from nodelens.workers.alerts.conditions.threshold import fires
from nodelens.workers.alerts.evaluator import evaluate, is_in_cooldown

# ── Operator dispatch ────────────────────────────────────────────


class TestCompareOperators:
    @pytest.mark.parametrize(
        ("cond", "value", "threshold", "expected"),
        [
            ("gt", 5.0, 4.0, True),
            ("gt", 4.0, 4.0, False),
            ("lt", 3.0, 4.0, True),
            ("gte", 4.0, 4.0, True),
            ("lte", 5.0, 4.0, False),
            ("eq", 4.0, 4.0, True),
            ("neq", 4.0, 4.0, False),
        ],
    )
    def test_known_ops(self, cond, value, threshold, expected):
        assert compare(cond, value, threshold) is expected

    def test_unknown_op_returns_false(self):
        assert compare("starts_with", 1.0, 1.0) is False


class TestFiresHelper:
    def test_none_value_does_not_fire(self):
        assert fires("gt", None, 1.0) is False

    def test_none_threshold_does_not_fire(self):
        assert fires("gt", 1.0, None) is False

    def test_both_present(self):
        assert fires("gt", 5.0, 1.0) is True


# ── Cooldown ─────────────────────────────────────────────────────


def _make_rule(**kwargs):
    rule = MagicMock()
    rule.id = kwargs.get("id", uuid.uuid4())
    rule.name = kwargs.get("name", "Test rule")
    rule.sensor_id = kwargs.get("sensor_id", uuid.uuid4())
    rule.rule_type = kwargs.get("rule_type", "instant")
    rule.condition = kwargs.get("condition", "gt")
    rule.threshold = kwargs.get("threshold", 10.0)
    rule.aggregation = kwargs.get("aggregation")
    rule.duration_seconds = kwargs.get("duration_seconds", 0)
    rule.cooldown_seconds = kwargs.get("cooldown_seconds", 300)
    rule.is_active = kwargs.get("is_active", True)
    return rule


def _scalar_result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


class TestCooldown:
    async def test_no_prior_fire_means_not_in_cooldown(self):
        rule = _make_rule(cooldown_seconds=300)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))
        now = datetime.now(UTC)
        assert await is_in_cooldown(session, rule, now) is False

    async def test_recent_fire_within_window_blocks(self):
        rule = _make_rule(cooldown_seconds=300)
        session = AsyncMock()
        last = datetime.now(UTC) - timedelta(seconds=60)
        session.execute = AsyncMock(return_value=_scalar_result(last))
        now = datetime.now(UTC)
        assert await is_in_cooldown(session, rule, now) is True

    async def test_old_fire_outside_window_does_not_block(self):
        rule = _make_rule(cooldown_seconds=60)
        session = AsyncMock()
        last = datetime.now(UTC) - timedelta(seconds=120)
        session.execute = AsyncMock(return_value=_scalar_result(last))
        now = datetime.now(UTC)
        assert await is_in_cooldown(session, rule, now) is False

    async def test_zero_cooldown_never_blocks(self):
        rule = _make_rule(cooldown_seconds=0)
        session = AsyncMock()
        # Note: with cooldown=0 we should short-circuit BEFORE querying.
        session.execute = AsyncMock(return_value=_scalar_result(datetime.now(UTC)))
        now = datetime.now(UTC)
        assert await is_in_cooldown(session, rule, now) is False
        session.execute.assert_not_called()


# ── End-to-end evaluation ────────────────────────────────────────


def _event(value: float = 0.0):
    return TelemetryEvent(
        device_id=str(uuid.uuid4()),
        sensor_id=str(uuid.uuid4()),
        value=value,
        timestamp=datetime.now(UTC),
    )


class TestEvaluateInstant:
    async def test_no_data_condition_returns_none(self):
        # The event-driven evaluator skips no_data; the periodic scanner
        # (no_data_scanner.py) owns evaluation for that condition. Receiving an
        # event also proves the sensor is not silent, so firing here would be
        # nonsensical.
        rule = _make_rule(condition="no_data")
        session = AsyncMock()
        result = await evaluate(session, rule, _event(0.0))
        assert result is None

    async def test_instant_fire_above_threshold(self):
        rule = _make_rule(condition="gt", threshold=10.0, cooldown_seconds=0)
        session = AsyncMock()
        # cooldown query path is short-circuited (cooldown_seconds=0)
        decision = await evaluate(session, rule, _event(15.0))
        assert decision is not None
        assert decision.triggered_value == 15.0
        assert "value 15.0" in decision.message

    async def test_instant_does_not_fire_below_threshold(self):
        rule = _make_rule(condition="gt", threshold=10.0, cooldown_seconds=0)
        session = AsyncMock()
        decision = await evaluate(session, rule, _event(5.0))
        assert decision is None

    async def test_cooldown_blocks_fire(self):
        rule = _make_rule(condition="gt", threshold=10.0, cooldown_seconds=300)
        session = AsyncMock()
        last = datetime.now(UTC) - timedelta(seconds=10)
        session.execute = AsyncMock(return_value=_scalar_result(last))
        decision = await evaluate(session, rule, _event(15.0))
        assert decision is None

    async def test_unknown_rule_type_returns_none(self):
        rule = _make_rule(rule_type="exotic", condition="gt", threshold=10.0, cooldown_seconds=0)
        session = AsyncMock()
        decision = await evaluate(session, rule, _event(15.0))
        assert decision is None


class TestEvaluateAggregated:
    async def test_aggregated_fire(self):
        rule = _make_rule(
            rule_type="aggregated",
            condition="gt",
            threshold=10.0,
            aggregation="avg",
            duration_seconds=60,
            cooldown_seconds=0,
        )
        session = AsyncMock()
        # _aggregate_value queries the telemetry table; return 20.0
        session.execute = AsyncMock(return_value=_scalar_result(20.0))
        decision = await evaluate(session, rule, _event(0.0))
        assert decision is not None
        assert decision.triggered_value == 20.0
        assert "avg(value)" in decision.message

    async def test_aggregated_no_data_returns_none(self):
        # Aggregated rule whose window has no telemetry — agg returns None,
        # `fires()` short-circuits, no decision. Distinct from the
        # condition='no_data' code path which is owned by the scanner.
        rule = _make_rule(
            rule_type="aggregated",
            condition="gt",
            threshold=10.0,
            aggregation="avg",
            duration_seconds=60,
            cooldown_seconds=0,
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))
        decision = await evaluate(session, rule, _event(0.0))
        assert decision is None

    async def test_unknown_aggregation_returns_none(self):
        rule = _make_rule(
            rule_type="aggregated",
            condition="gt",
            threshold=10.0,
            aggregation="nonsense",
            duration_seconds=60,
            cooldown_seconds=0,
        )
        session = AsyncMock()
        decision = await evaluate(session, rule, _event(0.0))
        assert decision is None
