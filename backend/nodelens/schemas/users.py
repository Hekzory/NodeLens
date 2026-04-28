"""Pydantic models for the /api/users admin endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=72)
    is_active: bool = True


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(
        default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$"
    )
    is_active: bool | None = None


class AdminPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=8, max_length=72)
