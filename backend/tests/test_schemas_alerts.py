"""Validation tests for AlertRuleCreate schema."""

import pytest
from pydantic import ValidationError

from nodelens.schemas.alerts import AlertRuleCreate
from tests.conftest import SENSOR_ID

_BASE = {"name": "x", "sensor_id": SENSOR_ID, "threshold": 1.0}


class TestAlertRuleCreate:
    @pytest.mark.parametrize(
        "condition",
        ["gt", "lt", "gte", "lte", "eq", "neq"],
    )
    def test_threshold_conditions_accept(self, condition):
        rule = AlertRuleCreate(**_BASE, condition=condition)
        assert rule.condition == condition

    @pytest.mark.parametrize(
        ("duration", "aggregation", "should_pass", "match"),
        [
            (60, None, True, None),
            (0, None, False, "duration_seconds > 0"),
            (60, "avg", False, "aggregation is not allowed"),
            (60, "sum", False, "aggregation is not allowed"),
        ],
    )
    def test_no_data_invariants(self, duration, aggregation, should_pass, match):
        payload = {
            "name": "x",
            "sensor_id": SENSOR_ID,
            "condition": "no_data",
            "duration_seconds": duration,
            "aggregation": aggregation,
        }
        if should_pass:
            rule = AlertRuleCreate(**payload)
            assert rule.condition == "no_data"
            assert rule.duration_seconds == duration
        else:
            with pytest.raises(ValidationError, match=match):
                AlertRuleCreate(**payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("name", ""),
            ("name", "x" * 256),
            ("description", "x" * 1001),
            ("severity", "fatal"),
            ("rule_type", "exotic"),
            ("condition", "starts_with"),
            ("duration_seconds", -1),
            ("cooldown_seconds", -1),
        ],
    )
    def test_field_constraints_reject(self, field, value):
        payload = {**_BASE, "condition": "gt", field: value}
        with pytest.raises(ValidationError):
            AlertRuleCreate(**payload)

    def test_defaults_applied(self):
        rule = AlertRuleCreate(**_BASE, condition="gt")
        assert rule.rule_type == "instant"
        assert rule.severity == "warning"
        assert rule.is_active is True
        assert rule.duration_seconds == 0
        assert rule.cooldown_seconds == 300
        assert rule.aggregation is None
        assert rule.description is None
