"""Read the effective config for a plugin from the DB.

Called once per subprocess startup by ``run_single._run`` immediately before
``plugin.configure(...)``. The subprocess has direct DB access via
``async_session`` — no need to round-trip through the API.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from nodelens.db.models.plugin import Plugin
from nodelens.db.session import async_session
from nodelens.plugin_config.registry import parse_schema
from nodelens.plugin_config.service import effective_values

logger = logging.getLogger("nodelens.plugin_config")


async def load_effective_config(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the merged defaults+overrides dict to pass to ``configure()``.

    On the first boot of a freshly-installed plugin the DB row may not exist
    yet (the supervisor's bootstrap and the subprocess start race); in that
    case we fall back to the in-memory manifest's ``config_schema`` and
    return all defaults.
    """
    plugin_id = uuid.UUID(str(manifest["id"]))
    async with async_session() as session:
        row = (
            await session.execute(
                select(Plugin.config, Plugin.config_schema).where(Plugin.id == plugin_id)
            )
        ).first()

    if row is None:
        # First-boot race — DB row not yet upserted. Use the manifest schema
        # and return defaults. The next restart will see the real DB row.
        logger.info(
            "Plugin %s has no DB row yet; using manifest schema defaults.",
            manifest.get("name"),
        )
        schema = parse_schema(manifest.get("config_schema") or [])
        return effective_values(schema, {})

    stored, raw_schema = row
    try:
        schema = parse_schema(raw_schema or [])
    except ValueError:
        logger.warning(
            "Plugin %s has an invalid stored config_schema; falling back to manifest.",
            manifest.get("name"),
        )
        schema = parse_schema(manifest.get("config_schema") or [])
    return effective_values(schema, dict(stored or {}))
