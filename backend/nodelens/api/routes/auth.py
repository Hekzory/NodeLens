"""Authentication endpoints.

The session itself is a signed cookie managed by Starlette's
``SessionMiddleware`` (mounted in ``api/app.py``); we only mutate
``request.session`` here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.auth.dependencies import get_current_user, get_current_user_optional
from nodelens.auth.security import hash_password, verify_password
from nodelens.db.models import User
from nodelens.schemas.auth import (
    AuthStatus,
    LoginRequest,
    PasswordChangeRequest,
    SetupRequest,
    UserRead,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _user_count(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count(User.id)))).scalar() or 0)


@router.get("/status", response_model=AuthStatus)
async def auth_status(
    db: AsyncSession = Depends(get_db),
    current: User | None = Depends(get_current_user_optional),
):
    """Public probe used by the frontend to choose between /setup, /login, app."""
    count = await _user_count(db)
    return AuthStatus(
        setup_required=count == 0,
        authenticated=current is not None,
        user=UserRead.model_validate(current) if current else None,
    )


@router.post("/setup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def setup(
    body: SetupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """One-time first-run setup. Returns 409 once any user exists."""
    if (await _user_count(db)) > 0:
        raise HTTPException(status_code=409, detail="Setup already completed")

    now = datetime.now(UTC)
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_active=True,
        last_login_at=now,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken") from exc
    await db.refresh(user)

    request.session["user_id"] = str(user.id)
    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.username == body.username)
    user = (await db.execute(stmt)).scalar_one_or_none()
    invalid = HTTPException(status_code=401, detail="Invalid username or password")
    if user is None or not user.is_active:
        raise invalid
    if not verify_password(body.password, user.password_hash):
        raise invalid

    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)

    request.session["user_id"] = str(user.id)
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    _user: User = Depends(get_current_user),
):
    request.session.clear()


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    return UserRead.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
