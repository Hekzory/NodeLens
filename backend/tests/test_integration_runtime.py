"""Round-trip and validation tests for SDK integration_runtime helpers."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from nodelens.schemas.events import AlertMessage
from nodelens.sdk.integration_runtime import (
    _decode_alert_message,
    encode_dispatch_event,
)


def _msg(triggered_at: datetime | None = None) -> AlertMessage:
    return AlertMessage(
        rule_name="r",
        device_name="d",
        triggered_value=42.5,
        message="m",
        triggered_at=triggered_at or datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
    )


class TestEncodeDispatchEvent:
    def test_returns_only_strings(self):
        fields = encode_dispatch_event(
            plugin_id="p",
            channel_id="c",
            channel_config={"to": "x"},
            message=_msg(),
        )
        assert set(fields) == {
            "plugin_id",
            "channel_id",
            "channel_config_json",
            "alert_message_json",
        }
        for v in fields.values():
            assert isinstance(v, str)
        assert json.loads(fields["channel_config_json"]) == {"to": "x"}
        assert isinstance(json.loads(fields["alert_message_json"]), dict)

    def test_includes_plugin_and_channel_ids(self):
        fields = encode_dispatch_event(
            plugin_id="plug-1",
            channel_id="chan-1",
            channel_config={},
            message=_msg(),
        )
        assert fields["plugin_id"] == "plug-1"
        assert fields["channel_id"] == "chan-1"

    @pytest.mark.parametrize("tz_offset_hours", [0, 3, -8])
    def test_round_trip_preserves_message(self, tz_offset_hours):
        tz = timezone(timedelta(hours=tz_offset_hours))
        original = _msg(triggered_at=datetime(2026, 4, 27, 12, 0, tzinfo=tz))
        fields = encode_dispatch_event(
            plugin_id="p",
            channel_id="c",
            channel_config={"to": "x"},
            message=original,
        )
        decoded = _decode_alert_message(fields["alert_message_json"])
        assert decoded == original


class TestDecodeAlertMessage:
    @pytest.mark.parametrize(
        ("payload", "exc"),
        [
            ('{"rule_name": "r"}', KeyError),
            ("not json", json.JSONDecodeError),
        ],
    )
    def test_malformed_raises(self, payload, exc):
        with pytest.raises(exc):
            _decode_alert_message(payload)
