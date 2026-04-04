"""Tests for write_batch validation pipeline.

All DB and insert helpers are mocked so these remain pure unit tests.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import nodelens.workers.ingestor.writer as writer_module
from nodelens.schemas.events import TelemetryEvent
from tests.conftest import DEVICE_ID, DEVICE_ID_STR, SENSOR_ID, SENSOR_ID_STR

DEVICE_ID_2 = uuid.UUID("20000000-0000-0000-0000-000000000002")
SENSOR_ID_2 = uuid.UUID("30000000-0000-0000-0000-000000000002")

_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _event(device_id=DEVICE_ID_STR, sensor_id=SENSOR_ID_STR, value=25.0, timestamp=_TS):
    return TelemetryEvent(device_id=device_id, sensor_id=sensor_id, value=value, timestamp=timestamp)


def _patch_helpers(sensor_device_map=None, valid_device_ids=None, insert_return=0):
    """Return a context-manager stack that patches all DB helpers."""
    if sensor_device_map is None:
        sensor_device_map = {}
    if valid_device_ids is None:
        valid_device_ids = set()

    return (
        patch.object(writer_module, "_load_mappings", AsyncMock(return_value=(sensor_device_map, valid_device_ids))),
        patch.object(writer_module, "_insert_rows", AsyncMock(return_value=insert_return)),
        patch.object(writer_module, "_update_last_seen", AsyncMock()),
    )


class TestWriteBatchUUIDParsing:
    async def test_invalid_uuid_event_is_dropped_before_db_lookup(self):
        event = _event(device_id="not-a-uuid", sensor_id="also-not-a-uuid")
        load_mock = AsyncMock(return_value=({}, set()))

        with patch.object(writer_module, "_load_mappings", load_mock):
            result = await writer_module.write_batch([event])

        assert result == 0
        load_mock.assert_not_called()

    async def test_valid_uuid_event_proceeds_to_db_lookup(self):
        # Sensor not in DB → returns 0, but _load_mappings IS called
        load_mock = AsyncMock(return_value=({}, set()))
        insert_mock = AsyncMock(return_value=0)

        with patch.object(writer_module, "_load_mappings", load_mock), \
             patch.object(writer_module, "_insert_rows", insert_mock), \
             patch.object(writer_module, "_update_last_seen", AsyncMock()):
            await writer_module.write_batch([_event()])

        load_mock.assert_called_once()


class TestWriteBatchValidation:
    async def test_skips_event_when_sensor_not_in_db(self):
        # Sensor absent from sensor_device_map
        load, insert, update = _patch_helpers(
            sensor_device_map={},
            valid_device_ids={DEVICE_ID},
        )
        with load, insert as insert_mock, update:
            result = await writer_module.write_batch([_event()])

        assert result == 0
        insert_mock.assert_not_called()

    async def test_skips_event_when_sensor_belongs_to_different_device(self):
        # SENSOR_ID is registered under DEVICE_ID but event claims DEVICE_ID_2
        sensor_device_map = {SENSOR_ID: DEVICE_ID}
        event = _event(device_id=str(DEVICE_ID_2), sensor_id=SENSOR_ID_STR)
        load, insert, update = _patch_helpers(
            sensor_device_map=sensor_device_map,
            valid_device_ids={DEVICE_ID, DEVICE_ID_2},
        )
        with load, insert as insert_mock, update:
            result = await writer_module.write_batch([event])

        assert result == 0
        insert_mock.assert_not_called()

    async def test_skips_event_when_device_not_in_valid_devices(self):
        # Sensor mapping exists but device is not in valid_device_ids
        sensor_device_map = {SENSOR_ID: DEVICE_ID}
        load, insert, update = _patch_helpers(
            sensor_device_map=sensor_device_map,
            valid_device_ids=set(),  # DEVICE_ID not present
        )
        with load, insert as insert_mock, update:
            result = await writer_module.write_batch([_event()])

        assert result == 0
        insert_mock.assert_not_called()

    async def test_returns_zero_when_all_events_are_invalid(self):
        events = [
            _event(device_id="bad-uuid-1"),
            _event(sensor_id="bad-uuid-2"),
        ]
        load_mock = AsyncMock(return_value=({}, set()))
        insert_mock = AsyncMock(return_value=0)

        with patch.object(writer_module, "_load_mappings", load_mock), \
             patch.object(writer_module, "_insert_rows", insert_mock):
            result = await writer_module.write_batch(events)

        assert result == 0
        load_mock.assert_not_called()
        insert_mock.assert_not_called()


class TestWriteBatchLastSeenTracking:
    async def test_tracks_latest_timestamp_per_device(self):
        ts_old = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        ts_new = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)

        events = [
            _event(timestamp=ts_old),
            _event(timestamp=ts_new),
        ]
        sensor_device_map = {SENSOR_ID: DEVICE_ID}
        captured: dict = {}

        async def capture_last_seen(affected):
            captured.update(affected)

        with patch.object(writer_module, "_load_mappings", AsyncMock(return_value=(sensor_device_map, {DEVICE_ID}))), \
             patch.object(writer_module, "_insert_rows", AsyncMock(return_value=2)), \
             patch.object(writer_module, "_update_last_seen", AsyncMock(side_effect=capture_last_seen)):
            await writer_module.write_batch(events)

        assert captured[DEVICE_ID] == ts_new

    async def test_out_of_order_events_do_not_regress_last_seen(self):
        ts_early = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)
        ts_late = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)

        # Deliver late event first, then early event
        events = [
            _event(timestamp=ts_late),
            _event(timestamp=ts_early),
        ]
        sensor_device_map = {SENSOR_ID: DEVICE_ID}
        captured: dict = {}

        async def capture_last_seen(affected):
            captured.update(affected)

        with patch.object(writer_module, "_load_mappings", AsyncMock(return_value=(sensor_device_map, {DEVICE_ID}))), \
             patch.object(writer_module, "_insert_rows", AsyncMock(return_value=2)), \
             patch.object(writer_module, "_update_last_seen", AsyncMock(side_effect=capture_last_seen)):
            await writer_module.write_batch(events)

        # Should keep the maximum timestamp
        assert captured[DEVICE_ID] == ts_late

    async def test_update_last_seen_not_called_when_nothing_written(self):
        # All events fail validation → no write → no last_seen update
        update_mock = AsyncMock()
        load, insert, _ = _patch_helpers(sensor_device_map={}, valid_device_ids=set())
        with load, insert, patch.object(writer_module, "_update_last_seen", update_mock):
            await writer_module.write_batch([_event()])

        update_mock.assert_not_called()
