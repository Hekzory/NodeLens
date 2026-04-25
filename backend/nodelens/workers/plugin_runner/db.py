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


def get_active_plugin_ids() -> set[str]:
    """Return plugin IDs where is_active = True (synchronous)."""
    from sqlalchemy.orm import Session

    from nodelens.db.models.plugin import Plugin

    with Session(_engine) as session:
        result = session.execute(
            select(Plugin.id).where(Plugin.is_active.is_(True))
        )
        return {str(row.id) for row in result}


def ensure_plugin_rows(manifests: dict[str, dict]) -> None:
    """Bootstrap a row in ``plugins`` for every discovered manifest.

    On INSERT we set ``is_active=True`` so a freshly-installed plugin actually
    starts. On CONFLICT we only refresh ``display_name`` / ``version`` — never
    ``is_active`` — so an operator's manual toggle in the UI is preserved.

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
            stmt = (
                pg_insert(Plugin)
                .values(
                    id=_uuid.UUID(plugin_id),
                    plugin_type=manifest["type"],
                    module_name=manifest["name"],
                    display_name=manifest["display_name"],
                    version=manifest["version"],
                    is_active=True,
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "display_name": manifest["display_name"],
                        "version": manifest["version"],
                    },
                )
            )
            session.execute(stmt)