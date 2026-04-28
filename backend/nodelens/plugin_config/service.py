"""Per-plugin config — load / effective values / update / reset.

Stateless: each call hits the DB once. The data is queried only on detail-
page load and on plugin subprocess startup, so the cost is negligible and we
sidestep cross-process cache coherence (the api and plugins containers each
have their own connection pool).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import update as sa_update

from nodelens.db.models.plugin import Plugin
from nodelens.plugin_config.registry import PluginConfigField, parse_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PluginConfigValidationError(ValueError):
    """Raised by :func:`update` when one or more inputs fail validation.

    ``field_errors`` maps field key → human message; ``general`` is reserved
    for cross-field issues (none today; kept for parity with system_settings
    so the API error shape is stable).
    """

    def __init__(
        self,
        field_errors: dict[str, str] | None = None,
        general: str | None = None,
    ) -> None:
        self.field_errors = field_errors or {}
        self.general = general
        super().__init__(
            general
            or "; ".join(f"{k}: {v}" for k, v in self.field_errors.items())
        )


async def load(
    session: AsyncSession, plugin_id: uuid.UUID
) -> tuple[Plugin, list[PluginConfigField], dict[str, Any]] | None:
    """Return ``(plugin, parsed_schema, stored_config)`` or ``None``."""
    plugin = await session.get(Plugin, plugin_id)
    if plugin is None:
        return None
    schema = parse_schema(plugin.config_schema or [])
    stored = dict(plugin.config or {})
    return plugin, schema, stored


def effective_values(
    schema: list[PluginConfigField], stored: dict[str, Any]
) -> dict[str, Any]:
    """Merge stored overrides on top of schema defaults, post-coercion.

    A stored value that no longer coerces (e.g. schema's value_type changed
    after the override was set) falls back to the field default rather than
    crashing the form.
    """
    out: dict[str, Any] = {}
    for field in schema:
        if field.key in stored:
            try:
                out[field.key] = field.coerce(stored[field.key])
                continue
            except ValueError:
                pass
        out[field.key] = field.default
    return out


async def update(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Validate ``updates`` and merge them into ``plugins.config``.

    Returns the canonicalized values that were written. Raises
    :class:`PluginConfigValidationError` (422-shaped) if any input fails.
    Increments ``config_version`` on every successful write so the supervisor
    can detect the change and restart the subprocess.
    """
    loaded = await load(session, plugin_id)
    if loaded is None:
        raise LookupError(f"Plugin {plugin_id} not found")
    plugin, schema, stored = loaded
    by_key = {f.key: f for f in schema}

    field_errors: dict[str, str] = {}
    coerced: dict[str, Any] = {}
    for key, raw in updates.items():
        field = by_key.get(key)
        if field is None:
            field_errors[key] = "unknown field"
            continue
        # Empty-string secrets mean "preserve existing" — drop them silently.
        if field.value_type == "secret" and raw == "":
            continue
        try:
            value = field.coerce(raw)
            field.validate(value)
        except ValueError as exc:
            field_errors[key] = str(exc)
            continue
        coerced[key] = value

    if field_errors:
        raise PluginConfigValidationError(field_errors=field_errors)

    if not coerced:
        # Nothing to persist (e.g. user submitted only blank secrets). Still
        # bump version so the UI's "save" feels like a real action.
        await session.execute(
            sa_update(Plugin)
            .where(Plugin.id == plugin_id)
            .values(config_version=Plugin.config_version + 1)
        )
        return {}

    merged = {**stored, **coerced}
    await session.execute(
        sa_update(Plugin)
        .where(Plugin.id == plugin_id)
        .values(config=merged, config_version=Plugin.config_version + 1)
    )
    return coerced


async def reset(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    keys: list[str] | None,
) -> None:
    """Drop overrides so the schema defaults take over for the listed keys.

    ``keys is None`` clears every override at once. Bumps ``config_version``.
    """
    loaded = await load(session, plugin_id)
    if loaded is None:
        raise LookupError(f"Plugin {plugin_id} not found")
    _plugin, _schema, stored = loaded

    if keys is None:
        new_config: dict[str, Any] = {}
    else:
        new_config = {k: v for k, v in stored.items() if k not in set(keys)}

    await session.execute(
        sa_update(Plugin)
        .where(Plugin.id == plugin_id)
        .values(config=new_config, config_version=Plugin.config_version + 1)
    )


__all__ = [
    "PluginConfigValidationError",
    "load",
    "effective_values",
    "update",
    "reset",
]
