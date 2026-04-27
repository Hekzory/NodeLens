"""Tests for the DB-touching helpers inside ingestor.writer.

These cover the mocked-out functions that ``test_ingestor_writer.py`` patches:
``_load_mappings``, ``_insert_rows``, ``_insert_rows_individually``,
``_update_last_seen``. We mock the SQLAlchemy session and capture statements.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

import nodelens.workers.ingestor.writer as writer_module
from tests.conftest import DEVICE_ID, SENSOR_ID

DEVICE_ID_2 = uuid.UUID("20000000-0000-0000-0000-000000000002")
SENSOR_ID_2 = uuid.UUID("30000000-0000-0000-0000-000000000002")
_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _patch_async_session(execute_results):
    """Build a patcher that returns ``execute_results`` from session.execute().

    ``execute_results`` is a list — successive ``execute`` calls pop the next
    pre-built result. Each entry must be a MagicMock that already exposes
    whatever the production code reads (``__iter__``, ``rowcount``, …).
    """
    session = MagicMock()
    results_iter = iter(execute_results)
    session.execute = AsyncMock(side_effect=lambda *_a, **_kw: next(results_iter))

    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    begin_ctx = MagicMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=session)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    factory = MagicMock(return_value=session_ctx)
    return patch.object(writer_module, "async_session", factory), session


def _row(**kw):
    """Make a row-like object accessed via attribute lookup."""
    r = MagicMock()
    for k, v in kw.items():
        setattr(r, k, v)
    return r


class TestLoadMappings:
    async def test_returns_sensor_device_map_and_active_devices(self):
        sensor_rows = [
            _row(id=SENSOR_ID, device_id=DEVICE_ID),
            _row(id=SENSOR_ID_2, device_id=DEVICE_ID_2),
        ]
        device_rows = [_row(id=DEVICE_ID)]

        sensor_result = MagicMock()
        sensor_result.__iter__ = lambda self: iter(sensor_rows)
        device_result = MagicMock()
        device_result.__iter__ = lambda self: iter(device_rows)

        patcher, _ = _patch_async_session([sensor_result, device_result])
        with patcher:
            mapping, valid = await writer_module._load_mappings(
                {SENSOR_ID, SENSOR_ID_2}, {DEVICE_ID, DEVICE_ID_2}
            )

        assert mapping == {SENSOR_ID: DEVICE_ID, SENSOR_ID_2: DEVICE_ID_2}
        assert valid == {DEVICE_ID}

    async def test_handles_empty_results(self):
        empty_sensor = MagicMock()
        empty_sensor.__iter__ = lambda self: iter([])
        empty_device = MagicMock()
        empty_device.__iter__ = lambda self: iter([])

        patcher, _ = _patch_async_session([empty_sensor, empty_device])
        with patcher:
            mapping, valid = await writer_module._load_mappings({SENSOR_ID}, {DEVICE_ID})

        assert mapping == {}
        assert valid == set()


class TestInsertRows:
    async def test_returns_rowcount_from_pg_insert(self):
        result = MagicMock()
        result.rowcount = 3
        patcher, session = _patch_async_session([result])
        with patcher:
            written = await writer_module._insert_rows(
                [{"time": _TS, "sensor_id": SENSOR_ID, "value_numeric": 1.0, "value_text": None}]
            )

        assert written == 3
        session.execute.assert_awaited_once()


class TestInsertRowsIndividually:
    async def test_skips_rows_that_raise_integrity_error(self):
        # Two rows: the first inserts cleanly, the second raises IntegrityError.
        rows = [
            {"time": _TS, "sensor_id": SENSOR_ID, "value_numeric": 1.0, "value_text": None},
            {"time": _TS, "sensor_id": SENSOR_ID_2, "value_numeric": 2.0, "value_text": None},
        ]

        ok_result = MagicMock()
        ok_result.rowcount = 1
        results = iter([ok_result, IntegrityError("stmt", {}, Exception("dup"))])

        async def execute_side_effect(*_a, **_kw):
            v = next(results)
            if isinstance(v, IntegrityError):
                raise v
            return v

        session = MagicMock()
        session.execute = AsyncMock(side_effect=execute_side_effect)

        outer_ctx = MagicMock()
        outer_ctx.__aenter__ = AsyncMock(return_value=session)
        outer_ctx.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=outer_ctx)

        # begin_nested() is its own context; the failing row must not abort the outer txn.
        nested_ctx = MagicMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=session)

        async def nested_aexit(exc_type, exc, tb):
            # Real begin_nested suppresses by re-raising — IntegrityError is caught by writer code.
            return False

        nested_ctx.__aexit__ = AsyncMock(side_effect=nested_aexit)
        session.begin_nested = MagicMock(return_value=nested_ctx)

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(writer_module, "async_session", MagicMock(return_value=session_ctx)):
            written = await writer_module._insert_rows_individually(rows)

        assert written == 1


class TestUpdateLastSeen:
    async def test_executes_one_update_per_device(self):
        captured: list = []

        async def execute_side_effect(stmt):
            captured.append(stmt)
            return MagicMock()

        session = MagicMock()
        session.execute = AsyncMock(side_effect=execute_side_effect)

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        begin_ctx = MagicMock()
        begin_ctx.__aenter__ = AsyncMock(return_value=session)
        begin_ctx.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=begin_ctx)

        with patch.object(writer_module, "async_session", MagicMock(return_value=session_ctx)):
            await writer_module._update_last_seen({DEVICE_ID: _TS, DEVICE_ID_2: _TS})

        assert len(captured) == 2

    async def test_no_op_for_empty_dict(self):
        session = MagicMock()
        session.execute = AsyncMock()

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        begin_ctx = MagicMock()
        begin_ctx.__aenter__ = AsyncMock(return_value=session)
        begin_ctx.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=begin_ctx)

        with patch.object(writer_module, "async_session", MagicMock(return_value=session_ctx)):
            await writer_module._update_last_seen({})

        session.execute.assert_not_called()


class TestWriteBatchIntegrityFallback:
    async def test_uses_per_row_insert_when_batch_fails(self):
        from nodelens.schemas.events import TelemetryEvent
        from tests.conftest import DEVICE_ID_STR, SENSOR_ID_STR

        event = TelemetryEvent(
            device_id=DEVICE_ID_STR,
            sensor_id=SENSOR_ID_STR,
            value=1.0,
            timestamp=_TS,
        )
        load_mock = AsyncMock(return_value=({SENSOR_ID: DEVICE_ID}, {DEVICE_ID}))
        insert_mock = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("conflict")))
        per_row_mock = AsyncMock(return_value=1)
        update_mock = AsyncMock()

        with (
            patch.object(writer_module, "_load_mappings", load_mock),
            patch.object(writer_module, "_insert_rows", insert_mock),
            patch.object(writer_module, "_insert_rows_individually", per_row_mock),
            patch.object(writer_module, "_update_last_seen", update_mock),
        ):
            written = await writer_module.write_batch([event])

        assert written == 1
        per_row_mock.assert_awaited_once()
        update_mock.assert_awaited_once()


