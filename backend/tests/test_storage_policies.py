"""Tests for db.apply_storage_policies — verify SQL is issued idempotently."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nodelens.config import settings
from nodelens.db import apply_storage_policies


def _make_engine_with_recording_conn() -> tuple[MagicMock, list[str]]:
    """Engine whose `engine.begin()` yields a conn that records its SQL."""
    issued: list[str] = []

    conn = MagicMock()

    async def _execute(stmt, *_a, **_kw):
        issued.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        return MagicMock()

    conn.execute = AsyncMock(side_effect=_execute)

    begin_ctx = MagicMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=conn)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)

    engine = MagicMock()
    engine.begin = MagicMock(return_value=begin_ctx)
    return engine, issued


@pytest.mark.asyncio
async def test_emits_alter_table_with_segmentby_and_orderby():
    engine, issued = _make_engine_with_recording_conn()
    await apply_storage_policies(engine)

    alter = next((s for s in issued if "ALTER TABLE telemetry" in s), None)
    assert alter is not None
    assert "timescaledb.compress" in alter
    assert "compress_segmentby = 'sensor_id'" in alter
    assert "compress_orderby = 'time DESC'" in alter


@pytest.mark.asyncio
async def test_compression_policy_uses_configured_days():
    engine, issued = _make_engine_with_recording_conn()
    await apply_storage_policies(engine)

    add_compress = next((s for s in issued if "add_compression_policy" in s), None)
    assert add_compress is not None
    assert f"INTERVAL '{settings.COMPRESSION_AFTER_DAYS} days'" in add_compress
    assert "compress_after =>" in add_compress


@pytest.mark.asyncio
async def test_retention_policy_uses_configured_days():
    engine, issued = _make_engine_with_recording_conn()
    await apply_storage_policies(engine)

    add_retain = next((s for s in issued if "add_retention_policy" in s), None)
    assert add_retain is not None
    assert f"INTERVAL '{settings.RETENTION_DAYS} days'" in add_retain
    assert "drop_after =>" in add_retain


@pytest.mark.asyncio
async def test_remove_called_before_add_for_each_policy():
    """Drop+add ordering matters: re-add after re-init must come last so config edits stick."""
    engine, issued = _make_engine_with_recording_conn()
    await apply_storage_policies(engine)

    rm_compress_idx = next(i for i, s in enumerate(issued) if "remove_compression_policy" in s)
    add_compress_idx = next(i for i, s in enumerate(issued) if "add_compression_policy" in s)
    rm_retain_idx = next(i for i, s in enumerate(issued) if "remove_retention_policy" in s)
    add_retain_idx = next(i for i, s in enumerate(issued) if "add_retention_policy" in s)

    assert rm_compress_idx < add_compress_idx
    assert rm_retain_idx < add_retain_idx
    # remove_*_policy must use if_exists => TRUE so a fresh DB doesn't error
    assert "if_exists => TRUE" in issued[rm_compress_idx]
    assert "if_exists => TRUE" in issued[rm_retain_idx]
