"""Tests for ingestor event parsing — pure functions, no DB or Redis needed."""

from datetime import datetime

import pytest

from nodelens.redis.parse import parse_telemetry_event as _parse_event
from nodelens.redis.parse import partition_telemetry_batch
from nodelens.schemas.events import (
    RegisterDeviceEvent,
    RegisterPluginEvent,
    RegisterSensorEvent,
    TelemetryEvent,
)
from nodelens.workers.ingestor.registration import (
    _parse_register_device,
    _parse_register_plugin,
    _parse_register_sensor,
)
from tests.conftest import DEVICE_ID_STR, PLUGIN_ID_STR, SENSOR_ID_STR

_VALID_TELEMETRY = {
    "device_id": DEVICE_ID_STR,
    "sensor_id": SENSOR_ID_STR,
    "value": "23.5",
    "timestamp": "2024-01-01T12:00:00+00:00",
}


class TestParseTelemetryEvent:
    def test_valid_fields_produce_correct_types(self):
        event = _parse_event(_VALID_TELEMETRY)
        assert isinstance(event, TelemetryEvent)
        assert event.device_id == DEVICE_ID_STR
        assert event.sensor_id == SENSOR_ID_STR
        assert event.value == 23.5
        assert isinstance(event.timestamp, datetime)

    def test_integer_value_string_is_accepted(self):
        fields = {**_VALID_TELEMETRY, "value": "42"}
        event = _parse_event(fields)
        assert event.value == 42.0

    def test_missing_field_raises_keyerror(self):
        fields = {k: v for k, v in _VALID_TELEMETRY.items() if k != "value"}
        with pytest.raises(KeyError):
            _parse_event(fields)

    def test_non_numeric_value_raises_valueerror(self):
        fields = {**_VALID_TELEMETRY, "value": "not-a-number"}
        with pytest.raises(ValueError, match="could not convert string to float"):
            _parse_event(fields)

    def test_invalid_timestamp_raises_valueerror(self):
        fields = {**_VALID_TELEMETRY, "timestamp": "not-a-date"}
        with pytest.raises(ValueError, match="(?i)isoformat"):
            _parse_event(fields)


class TestPartitionTelemetryBatch:
    def test_empty_batch_returns_three_empty_lists(self):
        events, good, bad = partition_telemetry_batch([])
        assert events == []
        assert good == []
        assert bad == []

    def test_all_valid_messages(self):
        msgs = [
            ("1-0", _VALID_TELEMETRY),
            ("1-1", {**_VALID_TELEMETRY, "value": "1.0"}),
        ]
        events, good, bad = partition_telemetry_batch(msgs)
        assert len(events) == 2
        assert good == ["1-0", "1-1"]
        assert bad == []

    def test_separates_malformed_from_valid_preserving_order(self):
        msgs = [
            ("1-0", _VALID_TELEMETRY),
            ("1-1", {**_VALID_TELEMETRY, "value": "not-a-number"}),
            ("1-2", _VALID_TELEMETRY),
            ("1-3", {k: v for k, v in _VALID_TELEMETRY.items() if k != "device_id"}),
        ]
        events, good, bad = partition_telemetry_batch(msgs)
        assert len(events) == 2
        assert good == ["1-0", "1-2"]
        assert bad == ["1-1", "1-3"]

    def test_uses_caller_supplied_logger(self):
        from unittest.mock import MagicMock

        log = MagicMock(spec=["warning"])
        msgs = [("1-0", {})]  # missing every field → KeyError
        events, good, bad = partition_telemetry_batch(msgs, logger=log)
        assert events == []
        assert good == []
        assert bad == ["1-0"]
        log.warning.assert_called_once()


class TestParseRegisterPlugin:
    _VALID = {
        "event_type": "register_plugin",
        "plugin_id": PLUGIN_ID_STR,
        "plugin_type": "device",
        "module_name": "demo_sender",
        "display_name": "Demo Sender",
        "version": "0.1.0",
    }

    def test_valid_fields_produce_event(self):
        event = _parse_register_plugin(self._VALID)
        assert isinstance(event, RegisterPluginEvent)
        assert event.plugin_id == PLUGIN_ID_STR
        assert event.plugin_type == "device"
        assert event.module_name == "demo_sender"
        assert event.version == "0.1.0"

    def test_missing_required_field_raises_keyerror(self):
        fields = {k: v for k, v in self._VALID.items() if k != "module_name"}
        with pytest.raises(KeyError):
            _parse_register_plugin(fields)


class TestParseRegisterDevice:
    _VALID = {
        "device_id": DEVICE_ID_STR,
        "plugin_id": PLUGIN_ID_STR,
        "external_id": "dev-001",
        "name": "Living Room",
        "location": "Floor 1",
    }

    def test_valid_fields_with_location(self):
        event = _parse_register_device(self._VALID)
        assert isinstance(event, RegisterDeviceEvent)
        assert event.location == "Floor 1"

    def test_missing_location_defaults_to_empty_string(self):
        fields = {k: v for k, v in self._VALID.items() if k != "location"}
        event = _parse_register_device(fields)
        assert not event.location

    def test_missing_required_field_raises_keyerror(self):
        fields = {k: v for k, v in self._VALID.items() if k != "name"}
        with pytest.raises(KeyError):
            _parse_register_device(fields)


class TestParseRegisterSensor:
    _VALID = {
        "sensor_id": SENSOR_ID_STR,
        "device_id": DEVICE_ID_STR,
        "key": "temperature",
        "name": "Temperature",
        "unit": "°C",
        "value_type": "numeric",
    }

    def test_valid_fields_with_unit_and_value_type(self):
        event = _parse_register_sensor(self._VALID)
        assert isinstance(event, RegisterSensorEvent)
        assert event.unit == "°C"
        assert event.value_type == "numeric"

    def test_missing_unit_defaults_to_empty_string(self):
        fields = {k: v for k, v in self._VALID.items() if k != "unit"}
        event = _parse_register_sensor(fields)
        assert not event.unit

    def test_missing_value_type_defaults_to_numeric(self):
        fields = {k: v for k, v in self._VALID.items() if k != "value_type"}
        event = _parse_register_sensor(fields)
        assert event.value_type == "numeric"

    def test_missing_required_field_raises_keyerror(self):
        fields = {k: v for k, v in self._VALID.items() if k != "key"}
        with pytest.raises(KeyError):
            _parse_register_sensor(fields)
