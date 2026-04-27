"""Validation tests for dashboard / widget Pydantic schemas."""

import pytest
from pydantic import ValidationError

from nodelens.schemas.dashboards import (
    DashboardCreate,
    DashboardUpdate,
    WidgetCreate,
    WidgetUpdate,
)


class TestWidgetCreate:
    @pytest.mark.parametrize(
        "widget_type",
        ["chart", "gauge", "stat_card", "status"],
    )
    def test_all_widget_types_accepted(self, widget_type):
        w = WidgetCreate(widget_type=widget_type, title="ok")
        assert w.widget_type == widget_type

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("widget_type", "histogram", "Input should be"),
            ("title", "", "at least 1"),
            ("title", "x" * 256, "at most 255"),
        ],
    )
    def test_invalid_field_rejected(self, field, value, match):
        payload = {"widget_type": "chart", "title": "ok", field: value}
        with pytest.raises(ValidationError, match=match):
            WidgetCreate(**payload)

    def test_defaults_applied(self):
        w = WidgetCreate(widget_type="chart", title="ok")
        assert w.config == {}
        assert w.layout == {}
        assert w.sort_order == 0
        assert w.sensor_id is None


class TestWidgetUpdate:
    def test_all_fields_optional(self):
        u = WidgetUpdate()
        assert u.title is None
        assert u.widget_type is None
        assert u.sort_order is None

    def test_title_min_length_when_provided(self):
        with pytest.raises(ValidationError, match="at least 1"):
            WidgetUpdate(title="")


class TestDashboardCreate:
    @pytest.mark.parametrize(
        ("name", "description"),
        [
            ("ok", None),
            ("ok", "x" * 1000),
        ],
    )
    def test_valid_inputs_accepted(self, name, description):
        d = DashboardCreate(name=name, description=description)
        assert d.name == name
        assert d.is_default is False

    @pytest.mark.parametrize(
        ("name", "description", "match"),
        [
            ("", None, "at least 1"),
            ("x" * 256, None, "at most 255"),
            ("ok", "x" * 1001, "at most 1000"),
        ],
    )
    def test_invalid_inputs_rejected(self, name, description, match):
        with pytest.raises(ValidationError, match=match):
            DashboardCreate(name=name, description=description)


class TestDashboardUpdate:
    def test_partial_update_with_all_none(self):
        u = DashboardUpdate()
        assert u.name is None
        assert u.description is None
        assert u.is_default is None

    def test_name_min_length_when_provided(self):
        with pytest.raises(ValidationError, match="at least 1"):
            DashboardUpdate(name="")
