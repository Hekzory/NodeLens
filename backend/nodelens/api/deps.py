"""FastAPI dependency injection helpers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.db.session import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, auto-closing on exit."""
    async with async_session() as session:
        yield session
