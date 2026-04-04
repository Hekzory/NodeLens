"""Tests for registration upsert field coercion.

Verifies that empty-string fields from the event dataclasses are converted
to NULL (Python None) before being written to nullable DB columns.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import nodelens.workers.ingestor.registration as reg_module
from nodelens.schemas.events import RegisterDeviceEvent, RegisterSensorEvent
from tests.conftest import DEVICE_ID_STR, PLUGIN_ID_STR, SENSOR_ID_STR


def _make_session():
    """Build a mock that satisfies `async with async_session() as s, s.begin()`."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    begin = MagicMock()
    begin.__aenter__ = AsyncMock(return_value=None)
    begin.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=begin)
    session.execute = AsyncMock(return_value=None)
    return session


def _capturing_pg_insert(captured: dict):
    """Return a fake pg_insert that records the values dict."""
    def factory(table):
        stmt = MagicMock()

        def values(vals):
            captured.update(vals)
            inner = MagicMock()
            inner.on_conflict_do_update = MagicMock(return_value=MagicMock())
            return inner

        stmt.values = values
        return stmt

    return factory


class TestUpsertDeviceCoercion:
    async def test_empty_location_becomes_none(self):
        event = RegisterDeviceEvent(
            device_id=DEVICE_ID_STR,
            plugin_id=PLUGIN_ID_STR,
            external_id="ext-001",
            name="Test Device",
            location="",
        )
        captured: dict = {}
        session = _make_session()

        with patch.object(reg_module, "async_session", return_value=session), \
             patch.object(reg_module, "pg_insert", _capturing_pg_insert(captured)):
            await reg_module._upsert_device(event)

        assert captured.get("location") is None

    async def test_nonempty_location_is_preserved(self):
        event = RegisterDeviceEvent(
            device_id=DEVICE_ID_STR,
            plugin_id=PLUGIN_ID_STR,
            external_id="ext-001",
            name="Test Device",
            location="living-room",
        )
        captured: dict = {}
        session = _make_session()

        with patch.object(reg_module, "async_session", return_value=session), \
             patch.object(reg_module, "pg_insert", _capturing_pg_insert(captured)):
            await reg_module._upsert_device(event)

        assert captured.get("location") == "living-room"


class TestUpsertSensorCoercion:
    async def test_empty_unit_becomes_none(self):
        event = RegisterSensorEvent(
            sensor_id=SENSOR_ID_STR,
            device_id=DEVICE_ID_STR,
            key="temperature",
            name="Temperature",
            unit="",
        )
        captured: dict = {}
        session = _make_session()

        with patch.object(reg_module, "async_session", return_value=session), \
             patch.object(reg_module, "pg_insert", _capturing_pg_insert(captured)):
            await reg_module._upsert_sensor(event)

        assert captured.get("unit") is None

    async def test_nonempty_unit_is_preserved(self):
        event = RegisterSensorEvent(
            sensor_id=SENSOR_ID_STR,
            device_id=DEVICE_ID_STR,
            key="temperature",
            name="Temperature",
            unit="°C",
        )
        captured: dict = {}
        session = _make_session()

        with patch.object(reg_module, "async_session", return_value=session), \
             patch.object(reg_module, "pg_insert", _capturing_pg_insert(captured)):
            await reg_module._upsert_sensor(event)

        assert captured.get("unit") == "°C"
