import logging

from sqlalchemy import create_engine, select

from nodelens.config import settings

logger = logging.getLogger("nodelens.plugin_runner")

# Create a plain synchronous engine — no asyncpg, no event-loop conflicts
_engine = create_engine(
    settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://"),
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
)


def get_plugin_states() -> dict[str, tuple[bool, int]]:
    """Return ``{plugin_id: (is_active, config_version)}`` for every plugin row.

    Replaces the older ``get_active_plugin_ids`` — the supervisor needs both
    the activation flag and the config version on each poll so it can detect
    config changes and restart the affected subprocess.
    """
    from sqlalchemy.orm import Session

    from nodelens.db.models.plugin import Plugin

    with Session(_engine) as session:
        result = session.execute(
            select(Plugin.id, Plugin.is_active, Plugin.config_version)
        )
        return {str(row.id): (bool(row.is_active), int(row.config_version)) for row in result}


def ensure_plugin_rows(manifests: dict[str, dict]) -> None:
    """Bootstrap a row in ``plugins`` for every discovered manifest.

    On INSERT we set ``is_active=True`` so a freshly-installed plugin actually
    starts. On CONFLICT we refresh ``display_name`` / ``description`` /
    ``version`` / ``config_schema`` — never ``is_active``, ``config``, or
    ``config_version`` — so an operator's UI toggles and config overrides
    survive a plugin worker restart.

    Without this, the supervisor's ``is_active`` gate creates a chicken-and-egg
    deadlock: the plugin row only appears once the plugin publishes a
    registration event, but the plugin never starts because there is no row.
    """
    import uuid as _uuid

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.orm import Session

    from nodelens.db.models.plugin import Plugin

    if not manifests:
        return

    with Session(_engine) as session, session.begin():
        for plugin_id, manifest in manifests.items():
            description = (manifest.get("description") or "").strip() or None
            schema = list(manifest.get("config_schema") or [])
            stmt = (
                pg_insert(Plugin)
                .values(
                    id=_uuid.UUID(plugin_id),
                    plugin_type=manifest["type"],
                    module_name=manifest["name"],
                    display_name=manifest["display_name"],
                    description=description,
                    version=manifest["version"],
                    is_active=True,
                    config_schema=schema,
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "display_name": manifest["display_name"],
                        "description": description,
                        "version": manifest["version"],
                        "config_schema": schema,
                    },
                )
            )
            session.execute(stmt)
