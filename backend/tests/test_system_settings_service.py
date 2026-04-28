"""Unit tests for the system settings registry + RuntimeSettings service."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nodelens.system_settings import REGISTRY, RuntimeSettings, runtime_settings
from nodelens.system_settings.registry import (
    cross_field_invariants,
    iter_settings,
)
from nodelens.system_settings.service import SettingsValidationError

# ── Registry coercion / validation ─────────────────────────────────


class TestCoerce:
    def test_int_accepts_int_and_integral_float(self):
        spec = REGISTRY["retention_days"]
        assert spec.coerce(7) == 7
        assert spec.coerce(7.0) == 7

    def test_int_rejects_bool(self):
        # JSON booleans are technically ints in Python; we treat them strictly.
        with pytest.raises(ValueError, match="must be an integer, got bool"):
            REGISTRY["retention_days"].coerce(True)

    def test_int_rejects_non_integer_float(self):
        with pytest.raises(ValueError, match="must be an integer"):
            REGISTRY["retention_days"].coerce(7.5)

    def test_int_rejects_string(self):
        with pytest.raises(ValueError, match="must be an integer"):
            REGISTRY["retention_days"].coerce("365")


class TestValidate:
    def test_below_min_rejected(self):
        spec = REGISTRY["retention_days"]
        with pytest.raises(ValueError, match="must be >="):
            spec.validate(0)

    def test_above_max_rejected(self):
        spec = REGISTRY["retention_days"]
        with pytest.raises(ValueError, match="must be <="):
            spec.validate(spec.max + 1)

    def test_within_bounds_accepted(self):
        REGISTRY["retention_days"].validate(365)


def test_cross_field_compression_must_be_below_retention():
    with pytest.raises(ValueError, match="compression_after_days"):
        cross_field_invariants(
            {"retention_days": 7, "compression_after_days": 7}
        )


def test_cross_field_passes_when_compression_below_retention():
    cross_field_invariants(
        {"retention_days": 30, "compression_after_days": 7}
    )


def test_iter_settings_groups_in_canonical_order():
    groups = [s.group for s in iter_settings()]
    # storage first, then alerts, then devices, then ui
    storage_end = max(i for i, g in enumerate(groups) if g == "storage")
    alerts_start = min(i for i, g in enumerate(groups) if g == "alerts")
    devices_start = min(i for i, g in enumerate(groups) if g == "devices")
    ui_start = min(i for i, g in enumerate(groups) if g == "ui")
    assert storage_end < alerts_start < devices_start < ui_start


# ── RuntimeSettings cache + DB interaction ────────────────────────


def _service_with_db_rows(rows: dict[str, Any]) -> RuntimeSettings:
    """Build a fresh RuntimeSettings whose ``_reload`` reads from a fake DB."""
    svc = RuntimeSettings()
    fake_rows = []
    for key, value in rows.items():
        row = MagicMock()
        row.key = key
        row.value = value
        fake_rows.append(row)

    async def _fake_reload() -> None:
        out: dict[str, Any] = {}
        for spec in iter_settings():
            raw = rows.get(spec.key)
            if raw is None:
                out[spec.key] = spec.default
            else:
                out[spec.key] = spec.coerce(raw)
        svc._cache = out
        svc._loaded_at = time.monotonic()

    svc._reload = _fake_reload  # type: ignore[assignment]
    return svc


class TestRuntimeSettingsRead:
    async def test_default_when_db_row_missing(self):
        svc = _service_with_db_rows({})
        assert await svc.get_int("retention_days") == REGISTRY["retention_days"].default

    async def test_db_row_overrides_default(self):
        svc = _service_with_db_rows({"retention_days": 90})
        assert await svc.get_int("retention_days") == 90

    async def test_get_many_returns_subset(self):
        svc = _service_with_db_rows({"disk_budget_gb": 5})
        out = await svc.get_many("disk_budget_gb", "retention_days")
        assert out["disk_budget_gb"] == 5
        assert out["retention_days"] == REGISTRY["retention_days"].default

    async def test_unknown_key_raises(self):
        svc = _service_with_db_rows({})
        with pytest.raises(KeyError):
            await svc.get("does_not_exist")

    async def test_cache_avoids_double_reload(self):
        svc = _service_with_db_rows({})
        calls = {"n": 0}
        original = svc._reload

        async def counting():
            calls["n"] += 1
            await original()

        svc._reload = counting  # type: ignore[assignment]
        await svc.get_int("retention_days")
        await svc.get_int("retention_days")
        assert calls["n"] == 1

    async def test_invalidate_forces_reload(self):
        svc = _service_with_db_rows({})
        calls = {"n": 0}
        original = svc._reload

        async def counting():
            calls["n"] += 1
            await original()

        svc._reload = counting  # type: ignore[assignment]
        await svc.get_int("retention_days")
        svc.invalidate()
        await svc.get_int("retention_days")
        assert calls["n"] == 2


class TestRuntimeSettingsUpdate:
    async def test_unknown_key_raises_validation_error(self):
        svc = _service_with_db_rows({})
        with pytest.raises(SettingsValidationError) as ei:
            await svc.update({"made_up": 1}, session=AsyncMock())
        assert "made_up" in ei.value.field_errors

    async def test_out_of_range_raises_validation_error(self):
        svc = _service_with_db_rows({})
        with pytest.raises(SettingsValidationError) as ei:
            await svc.update({"retention_days": 0}, session=AsyncMock())
        assert "retention_days" in ei.value.field_errors

    async def test_cross_field_failure_returns_general_error(self):
        # Defaults: retention=365, compression=7. Setting retention=5 alone
        # would push compression (7) above retention (5).
        svc = _service_with_db_rows({})
        with pytest.raises(SettingsValidationError) as ei:
            await svc.update({"retention_days": 5}, session=AsyncMock())
        assert ei.value.general is not None
        assert "compression_after_days" in ei.value.general

    async def test_valid_update_writes_and_invalidates_cache(self):
        svc = _service_with_db_rows({})
        await svc.get_int("retention_days")  # warm cache
        assert svc._cache  # not empty

        session = AsyncMock()
        out = await svc.update({"disk_budget_gb": 50}, session=session)
        assert out == {"disk_budget_gb": 50}
        assert session.execute.await_count == 1
        # Cache cleared so the next read picks up the new value
        assert svc._cache == {}


class TestRuntimeSettingsReset:
    async def test_unknown_key_raises(self):
        svc = _service_with_db_rows({})
        with pytest.raises(SettingsValidationError):
            await svc.reset(["bogus"], session=AsyncMock())

    async def test_known_key_deletes_and_clears_cache(self):
        svc = _service_with_db_rows({"disk_budget_gb": 5})
        await svc.get_int("disk_budget_gb")  # warm
        session = AsyncMock()
        await svc.reset(["disk_budget_gb"], session=session)
        assert session.execute.await_count == 1
        assert svc._cache == {}


# ── Module-level singleton sanity ──────────────────────────────────


def test_module_singleton_exposes_runtime_settings():
    assert isinstance(runtime_settings, RuntimeSettings)
