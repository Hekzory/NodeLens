"""FastAPI auth dependencies.

The session cookie is managed by Starlette's ``SessionMiddleware`` (mounted in
``api/app.py``); we only read ``request.session["user_id"]`` here.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.db.models import User


async def _load_session_user(request: Request, db: AsyncSession) -> User | None:
    raw = request.session.get("user_id") if hasattr(request, "session") else None
    if not raw:
        return None
    try:
        uid = uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None
    user = await db.get(User, uid)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _load_session_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    return await _load_session_user(request, db)
