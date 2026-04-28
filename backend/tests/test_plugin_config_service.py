"""Unit tests for the per-plugin config registry + service layer."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nodelens import plugin_config
from nodelens.plugin_config.registry import (
    PluginConfigField,
    parse_schema,
    schema_to_jsonable,
)
from nodelens.plugin_config.service import (
    PluginConfigValidationError,
    effective_values,
    reset,
    update,
)

_PLUGIN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


# ── Schema parsing ─────────────────────────────────────────────────


class TestParseSchema:
    def test_valid_block_returns_fields(self):
        raw = [
            {"key": "host", "label": "Host", "value_type": "string", "default": ""},
            {"key": "port", "label": "Port", "value_type": "int", "default": 25, "min": 1, "max": 65535},
            {"key": "secret", "label": "Pwd", "value_type": "secret", "default": ""},
        ]
        fields = parse_schema(raw)
        assert len(fields) == 3
        assert fields[0].key == "host"
        assert fields[1].min == 1.0
        assert fields[2].value_type == "secret"

    def test_none_returns_empty(self):
        assert parse_schema(None) == []

    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            parse_schema({"not": "a list"})

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match=r"\[0\]: missing 'key'"):
            parse_schema([{"label": "x", "value_type": "string"}])

    def test_unknown_value_type_raises(self):
        with pytest.raises(ValueError, match="unknown value_type"):
            parse_schema([{"key": "x", "label": "X", "value_type": "bogus"}])

    def test_duplicate_key_raises(self):
        with pytest.raises(ValueError, match="duplicate key"):
            parse_schema([
                {"key": "x", "label": "X", "value_type": "string"},
                {"key": "x", "label": "X2", "value_type": "int"},
            ])

    def test_default_below_min_raises(self):
        with pytest.raises(ValueError, match="invalid default"):
            parse_schema([
                {"key": "x", "label": "X", "value_type": "int", "default": 0, "min": 1},
            ])

    def test_default_filled_when_omitted(self):
        fields = parse_schema([{"key": "x", "label": "X", "value_type": "bool"}])
        assert fields[0].default is False

    def test_round_trip_via_schema_to_jsonable(self):
        raw = [{"key": "host", "label": "Host", "value_type": "string", "default": "x"}]
        re_parsed = parse_schema(schema_to_jsonable(parse_schema(raw)))
        assert re_parsed[0].key == "host"
        assert re_parsed[0].default == "x"


# ── Coerce / validate ──────────────────────────────────────────────


class TestCoerceAndValidate:
    def test_secret_coerces_string_unchanged(self):
        f = PluginConfigField(key="k", label="K", group="g", value_type="secret", default="")
        assert f.coerce("hunter2") == "hunter2"

    def test_secret_rejects_non_string(self):
        f = PluginConfigField(key="k", label="K", group="g", value_type="secret", default="")
        with pytest.raises(ValueError, match="must be a string"):
            f.coerce(42)

    def test_int_below_min_rejected(self):
        f = PluginConfigField(key="k", label="K", group="g", value_type="int", default=10, min=5)
        with pytest.raises(ValueError, match="must be >="):
            f.validate(0)

    def test_bool_strict(self):
        f = PluginConfigField(key="k", label="K", group="g", value_type="bool", default=False)
        with pytest.raises(ValueError, match="must be a boolean"):
            f.coerce(0)


# ── effective_values ───────────────────────────────────────────────


def _mk_schema() -> list[PluginConfigField]:
    return parse_schema([
        {"key": "host", "label": "Host", "value_type": "string", "default": "localhost"},
        {"key": "port", "label": "Port", "value_type": "int", "default": 25},
        {"key": "use_tls", "label": "TLS", "value_type": "bool", "default": False},
        {"key": "pwd", "label": "Pwd", "value_type": "secret", "default": ""},
    ])


class TestEffectiveValues:
    def test_all_defaults_when_stored_empty(self):
        eff = effective_values(_mk_schema(), {})
        assert eff == {"host": "localhost", "port": 25, "use_tls": False, "pwd": ""}

    def test_overrides_replace_defaults(self):
        eff = effective_values(_mk_schema(), {"host": "smtp.example.com", "port": 587})
        assert eff["host"] == "smtp.example.com"
        assert eff["port"] == 587
        assert eff["use_tls"] is False  # untouched

    def test_uncoercible_stored_falls_back_to_default(self):
        # A persisted "abc" for an int field should not crash — fall back.
        eff = effective_values(_mk_schema(), {"port": "abc"})
        assert eff["port"] == 25


# ── update / reset ─────────────────────────────────────────────────


def _mock_session(stored: dict[str, Any], schema_jsonable: list[dict]):
    """Build an AsyncSession-like mock that returns one Plugin row from .get()."""
    session = AsyncMock()
    plugin = MagicMock()
    plugin.id = _PLUGIN_ID
    plugin.config = stored
    plugin.config_schema = schema_jsonable
    plugin.config_version = 0
    session.get = AsyncMock(return_value=plugin)
    session.execute = AsyncMock()
    return session, plugin


class TestUpdate:
    async def test_unknown_key_raises_validation_error(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({}, schema)
        with pytest.raises(PluginConfigValidationError) as ei:
            await update(session, _PLUGIN_ID, {"made_up": 1})
        assert "made_up" in ei.value.field_errors

    async def test_out_of_range_int_raises(self):
        schema_extra = schema_to_jsonable(parse_schema([
            {"key": "n", "label": "N", "value_type": "int", "default": 10, "min": 1, "max": 100},
        ]))
        session, _ = _mock_session({}, schema_extra)
        with pytest.raises(PluginConfigValidationError) as ei:
            await update(session, _PLUGIN_ID, {"n": 9999})
        assert "n" in ei.value.field_errors

    async def test_type_mismatch_raises(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({}, schema)
        with pytest.raises(PluginConfigValidationError) as ei:
            await update(session, _PLUGIN_ID, {"port": "abc"})
        assert "port" in ei.value.field_errors

    async def test_secret_empty_string_is_no_op_but_bumps_version(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({"pwd": "existing"}, schema)
        coerced = await update(session, _PLUGIN_ID, {"pwd": ""})
        assert coerced == {}
        # Single UPDATE issued (just bumps version)
        assert session.execute.await_count == 1

    async def test_valid_update_writes_and_increments_version(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({}, schema)
        coerced = await update(session, _PLUGIN_ID, {"host": "smtp.test"})
        assert coerced == {"host": "smtp.test"}
        assert session.execute.await_count == 1

    async def test_unknown_plugin_raises_lookup_error(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(LookupError):
            await update(session, _PLUGIN_ID, {"host": "x"})


class TestReset:
    async def test_reset_all_clears_dict(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({"host": "x", "port": 9}, schema)
        await reset(session, _PLUGIN_ID, None)
        assert session.execute.await_count == 1

    async def test_reset_one_key_keeps_others(self):
        schema = schema_to_jsonable(_mk_schema())
        session, _ = _mock_session({"host": "x", "port": 9}, schema)
        await reset(session, _PLUGIN_ID, ["host"])
        assert session.execute.await_count == 1


# ── Public surface ────────────────────────────────────────────────


def test_module_reexports():
    assert plugin_config.PluginConfigField is PluginConfigField
    assert plugin_config.parse_schema is parse_schema
