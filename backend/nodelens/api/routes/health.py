"""Health & readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens import __version__
from nodelens.api.deps import get_db
from nodelens.redis.client import get_redis

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    """Basic liveness check."""
    return {"status": "ok", "version": __version__}


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """Verify database connectivity."""
    result = await db.execute(text("SELECT 1"))
    row = result.scalar()
    return {"status": "ok" if row == 1 else "degraded", "version": __version__}


@router.get("/redis")
async def health_redis():
    """Verify Redis connectivity."""
    r = await get_redis()
    pong = await r.ping()
    return {"status": "ok" if pong else "degraded", "version": __version__}
