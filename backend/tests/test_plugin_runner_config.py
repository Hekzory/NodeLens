"""Tests for plugin-runner config helpers (load_effective_config + states)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nodelens.plugin_config import subprocess_loader
from nodelens.plugin_config.registry import parse_schema, schema_to_jsonable

_PID = "10000000-0000-0000-0000-000000000001"


def _schema() -> list[dict[str, Any]]:
    return schema_to_jsonable(parse_schema([
        {"key": "host", "label": "Host", "value_type": "string", "default": "localhost"},
        {"key": "port", "label": "Port", "value_type": "int", "default": 25, "min": 1, "max": 65535},
    ]))


class _AsyncSessionCM:
    """Tiny async context manager that yields a fixed session mock."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_):
        return False


def _mock_async_session_factory(execute_first):
    """Return a callable usable as a drop-in for ``async_session``."""
    session = MagicMock()
    result = MagicMock()
    result.first.return_value = execute_first

    async def _execute(_):
        return result

    session.execute = _execute
    return lambda: _AsyncSessionCM(session)


@pytest.mark.asyncio
async def test_load_effective_config_merges_defaults_and_overrides():
    manifest = {"id": _PID, "name": "x", "config_schema": _schema()}
    factory = _mock_async_session_factory(execute_first=({"host": "smtp.example"}, _schema()))
    with patch.object(subprocess_loader, "async_session", factory):
        eff = await subprocess_loader.load_effective_config(manifest)
    assert eff["host"] == "smtp.example"
    assert eff["port"] == 25  # default kept


@pytest.mark.asyncio
async def test_load_effective_config_first_boot_falls_back_to_manifest_schema():
    manifest = {"id": _PID, "name": "x", "config_schema": _schema()}
    factory = _mock_async_session_factory(execute_first=None)
    with patch.object(subprocess_loader, "async_session", factory):
        eff = await subprocess_loader.load_effective_config(manifest)
    assert eff == {"host": "localhost", "port": 25}


@pytest.mark.asyncio
async def test_load_effective_config_invalid_db_schema_falls_back_to_manifest():
    manifest = {"id": _PID, "name": "x", "config_schema": _schema()}
    bad_db_schema = [{"this is": "garbage"}]
    factory = _mock_async_session_factory(execute_first=({}, bad_db_schema))
    with patch.object(subprocess_loader, "async_session", factory):
        eff = await subprocess_loader.load_effective_config(manifest)
    assert eff == {"host": "localhost", "port": 25}


def test_get_plugin_states_signature():
    """Smoke-import to make sure renaming ``get_active_plugin_ids`` did not
    leave a dangling import elsewhere in the supervisor module path."""
    from nodelens.workers.plugin_runner import db as runner_db

    assert hasattr(runner_db, "get_plugin_states")
    assert not hasattr(runner_db, "get_active_plugin_ids")
