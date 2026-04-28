"""User-management endpoints (admin UI).

All routes are gated by ``get_current_user`` at ``include_router`` time in
``api/app.py``. There are no roles for v1 — any authenticated user can manage
the user roster.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.auth.dependencies import get_current_user
from nodelens.auth.security import hash_password
from nodelens.db.models import User
from nodelens.schemas.auth import UserRead
from nodelens.schemas.users import AdminPasswordReset, UserCreate, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


async def _active_count(db: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(User.is_active.is_(True))
    return int((await db.execute(stmt)).scalar() or 0)


@router.get("", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(User).order_by(User.created_at.asc()))
    ).scalars().all()
    return [UserRead.model_validate(u) for u in rows]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_active=body.is_active,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken") from exc
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)

    # Refuse to deactivate the last active user (protects against lock-out).
    if update_data.get("is_active") is False and user.is_active:
        active = await _active_count(db)
        if active <= 1:
            raise HTTPException(
                status_code=400, detail="At least one active user is required"
            )

    # Refuse to deactivate yourself — same lock-out concern, more obvious UX.
    if (
        update_data.get("is_active") is False
        and user.id == current.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate the user you are logged in as",
        )

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken") from exc
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the user you are logged in as",
        )
    if user.is_active and (await _active_count(db)) <= 1:
        raise HTTPException(
            status_code=400, detail="At least one active user is required"
        )
    await db.delete(user)
    await db.commit()


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def admin_reset_password(
    user_id: uuid.UUID,
    body: AdminPasswordReset,
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
