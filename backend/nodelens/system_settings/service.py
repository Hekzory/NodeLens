"""In-process TTL cache + DB read/write layer for system settings.

Each Python process (api, ingestor, alerts, plugins) owns its own
``runtime_settings`` singleton with a ~30s cache. After a PATCH lands in the
api process, its own cache invalidates immediately; other processes pick up
the change on their next cache refresh. Settings whose call sites read
once-at-startup are flagged ``requires_restart`` in the registry and the
frontend shows a "restart required" badge.

Design notes:
- The cache stores all registry keys, populated lazily on first access.
- Reads are async (we hit Postgres on cache miss), so callers must await.
- The cache resolves a missing DB row to the registry default. Updates and
  resets clear the cache so the next read repopulates from DB.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from nodelens.db.models import SystemSetting
from nodelens.db.session import async_session
from nodelens.system_settings.registry import (
    REGISTRY,
    cross_field_invariants,
    iter_settings,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SettingsValidationError(ValueError):
    """Raised by `RuntimeSettings.update` when one or more keys are invalid.

    `field_errors` maps key → human message; `general` holds cross-field
    failures (e.g. compression>=retention) that don't belong to a single key.
    """

    def __init__(
        self,
        field_errors: dict[str, str] | None = None,
        general: str | None = None,
    ) -> None:
        self.field_errors = field_errors or {}
        self.general = general
        super().__init__(general or "; ".join(f"{k}: {v}" for k, v in self.field_errors.items()))


class RuntimeSettings:
    """Cached accessor for DB-overridable settings."""

    _TTL = 30.0

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._loaded_at: float = 0.0
        self._lock = asyncio.Lock()

    # ── public read API ─────────────────────────────────────────────

    async def get(self, key: str) -> Any:
        if key not in REGISTRY:
            raise KeyError(f"Unknown setting key: {key!r}")
        await self._ensure_fresh()
        return self._cache[key]

    async def get_int(self, key: str) -> int:
        return int(await self.get(key))

    async def get_many(self, *keys: str) -> dict[str, Any]:
        await self._ensure_fresh()
        return {k: self._cache[k] for k in keys}

    async def get_all(self) -> dict[str, Any]:
        """All registered keys with their current effective value."""
        await self._ensure_fresh()
        return dict(self._cache)

    def invalidate(self) -> None:
        self._cache = {}
        self._loaded_at = 0.0

    # ── public write API ────────────────────────────────────────────

    async def update(
        self, updates: dict[str, Any], session: AsyncSession | None = None
    ) -> dict[str, Any]:
        """Validate and persist a batch of overrides.

        Returns the canonicalized values written. Raises
        ``SettingsValidationError`` (422-shaped) before touching the DB if
        any input fails. Cache is invalidated on success.
        """
        if not updates:
            return {}

        field_errors: dict[str, str] = {}
        coerced: dict[str, Any] = {}
        for key, raw in updates.items():
            spec = REGISTRY.get(key)
            if spec is None:
                field_errors[key] = "unknown setting"
                continue
            try:
                value = spec.coerce(raw)
                spec.validate(value)
            except ValueError as exc:
                field_errors[key] = str(exc)
                continue
            coerced[key] = value

        if field_errors:
            raise SettingsValidationError(field_errors=field_errors)

        # Cross-field invariants need the *effective* state, so merge with
        # what we'd have after this update.
        effective = await self.get_all()
        effective.update(coerced)
        try:
            cross_field_invariants(effective)
        except ValueError as exc:
            raise SettingsValidationError(general=str(exc)) from None

        if session is None:
            async with async_session() as s, s.begin():
                await self._write(s, coerced)
        else:
            await self._write(session, coerced)

        self.invalidate()
        return coerced

    async def reset(self, keys: list[str], session: AsyncSession | None = None) -> None:
        """Drop DB rows so the registry default takes over for the listed keys."""
        unknown = [k for k in keys if k not in REGISTRY]
        if unknown:
            raise SettingsValidationError(
                field_errors=dict.fromkeys(unknown, "unknown setting")
            )
        if not keys:
            return

        if session is None:
            async with async_session() as s, s.begin():
                await s.execute(delete(SystemSetting).where(SystemSetting.key.in_(keys)))
        else:
            await session.execute(delete(SystemSetting).where(SystemSetting.key.in_(keys)))

        self.invalidate()

    # ── internals ───────────────────────────────────────────────────

    async def _ensure_fresh(self) -> None:
        if self._cache and (time.monotonic() - self._loaded_at) < self._TTL:
            return
        async with self._lock:
            if self._cache and (time.monotonic() - self._loaded_at) < self._TTL:
                return
            await self._reload()

    async def _reload(self) -> None:
        async with async_session() as s:
            rows = (await s.execute(select(SystemSetting))).scalars().all()
        db_values = {row.key: row.value for row in rows}

        out: dict[str, Any] = {}
        for spec in iter_settings():
            raw = db_values.get(spec.key)
            if raw is None:
                out[spec.key] = spec.default
                continue
            try:
                out[spec.key] = spec.coerce(raw)
            except ValueError:
                # A persisted row that can no longer be coerced is a sign that
                # the registry's value_type changed; fall back to the default.
                out[spec.key] = spec.default
        self._cache = out
        self._loaded_at = time.monotonic()

    async def _write(self, session: AsyncSession, coerced: dict[str, Any]) -> None:
        for key, value in coerced.items():
            stmt = (
                pg_insert(SystemSetting)
                .values(key=key, value=value)
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": value, "updated_at": _now()},
                )
            )
            await session.execute(stmt)


def _now():
    from datetime import UTC, datetime
    return datetime.now(UTC)


# Per-process singleton. Each container imports this and gets its own cache.
runtime_settings = RuntimeSettings()
