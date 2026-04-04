"""Shared fixtures for NodeLens unit tests."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

# ── Canonical test UUIDs ─────────────────────────────────────────
PLUGIN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
DEVICE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
SENSOR_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")

PLUGIN_ID_STR = str(PLUGIN_ID)
DEVICE_ID_STR = str(DEVICE_ID)
SENSOR_ID_STR = str(SENSOR_ID)


def make_execute_result(scalars_all=None, scalar_one_or_none=None, one=None):
    """Build a mock that mimics the result of AsyncSession.execute()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars_all or []
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar.return_value = 0
    if one is not None:
        result.one.return_value = one
    return result


def make_mock_db():
    """Return a mock AsyncSession suitable for API unit tests."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value=make_execute_result())
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=_refresh_side_effect)
    return db


async def _refresh_side_effect(obj):
    """Simulate DB refresh: set server-generated fields if not already set."""
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    now = datetime.now(UTC)
    if getattr(obj, "created_at", None) is None:
        obj.created_at = now
    if getattr(obj, "updated_at", None) is None:
        obj.updated_at = now
    if getattr(obj, "triggered_at", None) is None:
        obj.triggered_at = now
