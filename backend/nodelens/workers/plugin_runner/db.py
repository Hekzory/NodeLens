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