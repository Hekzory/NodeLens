"""Tests for the disk-budget enforcer (ingestor)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nodelens.workers.ingestor.retention import (
    HEADROOM_FRACTION,
    ChunkInfo,
    enforce_once,
    select_chunks_to_drop,
)

GB = 1024**3


def _chunks(*, count: int, each_bytes: int) -> list[ChunkInfo]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        ChunkInfo(range_end=base + timedelta(days=i + 1), total_bytes=each_bytes)
        for i in range(count)
    ]


class TestSelectChunksToDrop:
    def test_under_budget_returns_none(self):
        chunks = _chunks(count=3, each_bytes=1 * GB)
        assert select_chunks_to_drop(total_bytes=3 * GB, budget_bytes=30 * GB, chunks_oldest_first=chunks) is None

    def test_at_budget_returns_none(self):
        chunks = _chunks(count=3, each_bytes=10 * GB)
        assert select_chunks_to_drop(total_bytes=30 * GB, budget_bytes=30 * GB, chunks_oldest_first=chunks) is None

    def test_drops_until_headroom_satisfied(self):
        # 40 GB total, 30 GB budget → headroom target = 28.5 GB.
        # Drop chunk[0] → 30 (still > 28.5), drop chunk[1] → 20 (≤ 28.5). Two chunks dropped.
        chunks = _chunks(count=4, each_bytes=10 * GB)
        cutoff = select_chunks_to_drop(total_bytes=40 * GB, budget_bytes=30 * GB, chunks_oldest_first=chunks)
        assert cutoff == chunks[1].range_end

    def test_minimum_overage_still_drops_one(self):
        # 31 small chunks of 1 GB at 30 GB budget → headroom 28.5. Drop until ≤ 28.5.
        chunks = _chunks(count=31, each_bytes=1 * GB)
        cutoff = select_chunks_to_drop(total_bytes=31 * GB, budget_bytes=30 * GB, chunks_oldest_first=chunks)
        # Need to remove at least 2.5 GB → 3 chunks (chunks[0], chunks[1], chunks[2]).
        assert cutoff == chunks[2].range_end

    def test_drops_just_enough_to_hit_headroom(self):
        # 40 GB total, 20 GB budget → headroom target = 19 GB → must drop until projected ≤ 19 GB
        # Each chunk = 10 GB. Drop chunk[0] → 30, chunk[1] → 20, chunk[2] → 10. So drop 3 chunks.
        chunks = _chunks(count=4, each_bytes=10 * GB)
        cutoff = select_chunks_to_drop(total_bytes=40 * GB, budget_bytes=20 * GB, chunks_oldest_first=chunks)
        assert cutoff == chunks[2].range_end

    def test_headroom_is_95_percent(self):
        assert HEADROOM_FRACTION == 0.95

    def test_empty_chunks_returns_none_even_when_over(self):
        # Defensive: report says we are over, but DB shows no chunks. Don't crash.
        assert select_chunks_to_drop(total_bytes=99 * GB, budget_bytes=30 * GB, chunks_oldest_first=[]) is None

    def test_zero_budget_drops_everything(self):
        chunks = _chunks(count=3, each_bytes=1 * GB)
        cutoff = select_chunks_to_drop(total_bytes=3 * GB, budget_bytes=0, chunks_oldest_first=chunks)
        assert cutoff == chunks[-1].range_end  # newest range_end → all chunks dropped


class TestEnforceOnce:
    def _patch_session(self, total_bytes: int, chunks: list[ChunkInfo]) -> tuple[MagicMock, MagicMock]:
        """Build a mock async_session that returns the given totals + chunks."""
        executed: list[str] = []
        executed_params: list[dict] = []

        async def _execute(stmt, params=None):
            sql = str(stmt)
            executed.append(sql)
            executed_params.append(params or {})
            result = MagicMock()
            if "hypertable_size" in sql:
                result.scalar = MagicMock(return_value=total_bytes)
            elif "chunks_detailed_size" in sql:
                rows = [MagicMock(range_end=c.range_end, total_bytes=c.total_bytes) for c in chunks]
                result.all = MagicMock(return_value=rows)
            else:
                # drop_chunks call — return value is unused
                result.all = MagicMock(return_value=[])
                result.scalar = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        begin_ctx = MagicMock()
        begin_ctx.__aenter__ = AsyncMock(return_value=session)
        begin_ctx.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=begin_ctx)

        async_session_factory = MagicMock(return_value=session_ctx)

        sentinel = MagicMock()
        sentinel.executed = executed
        sentinel.executed_params = executed_params
        return async_session_factory, sentinel

    @pytest.mark.asyncio
    async def test_under_budget_no_drop(self):
        chunks = _chunks(count=2, each_bytes=1 * GB)
        factory, sentinel = self._patch_session(total_bytes=2 * GB, chunks=chunks)
        # disk_budget_gb default is 30 (from REGISTRY); the autouse fixture in
        # conftest seeds runtime_settings._cache so enforce_once() reads it
        # without hitting a real DB.
        with patch("nodelens.workers.ingestor.retention.async_session", factory):
            await enforce_once()
        # Only the size query — no chunk listing, no drop.
        assert any("hypertable_size" in s for s in sentinel.executed)
        assert not any("drop_chunks" in s for s in sentinel.executed)

    @pytest.mark.asyncio
    async def test_over_budget_calls_drop_chunks_with_cutoff(self):
        chunks = _chunks(count=4, each_bytes=10 * GB)  # 40 GB
        factory, sentinel = self._patch_session(total_bytes=40 * GB, chunks=chunks)
        # disk_budget_gb default is 30 (from REGISTRY); the autouse fixture in
        # conftest seeds runtime_settings._cache so enforce_once() reads it
        # without hitting a real DB.
        with patch("nodelens.workers.ingestor.retention.async_session", factory):
            await enforce_once()

        drop_calls = [
            (sql, p) for sql, p in zip(sentinel.executed, sentinel.executed_params, strict=False)
            if "drop_chunks" in sql
        ]
        assert len(drop_calls) == 1
        # 40 GB total, 30 GB budget → target 28.5 GB → drop chunks[0]+[1] → cutoff=chunks[1].
        assert drop_calls[0][1]["cutoff"] == chunks[1].range_end

    @pytest.mark.asyncio
    async def test_over_budget_with_no_chunks_does_not_drop(self):
        # hypertable_size reports we are over, but chunks_detailed_size is empty.
        # Must log a warning and return without calling drop_chunks.
        factory, sentinel = self._patch_session(total_bytes=40 * GB, chunks=[])
        # disk_budget_gb default is 30 (from REGISTRY); the autouse fixture in
        # conftest seeds runtime_settings._cache so enforce_once() reads it
        # without hitting a real DB.
        with patch("nodelens.workers.ingestor.retention.async_session", factory):
            await enforce_once()

        # We listed chunks (the function reached the over-budget branch) …
        assert any("chunks_detailed_size" in s for s in sentinel.executed)
        # … but never tried to drop anything.
        assert not any("drop_chunks" in s for s in sentinel.executed)
