"""Pydantic models for the /api/auth endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    """Public projection of a ``users`` row. Never includes ``password_hash``."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class SetupRequest(BaseModel):
    """First-run setup payload. Only valid while the ``users`` table is empty."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=72)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class AuthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_required: bool
    authenticated: bool
    user: UserRead | None = None
