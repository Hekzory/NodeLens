"""Pydantic schemas for dashboard and widget API."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Widgets ─────────────────────────────────────────────────────

class WidgetCreate(BaseModel):
    """Request body to create a widget on a dashboard."""

    widget_type: Literal["chart", "gauge", "stat_card", "status"]
    title: str = Field(min_length=1, max_length=255)
    sensor_id: uuid.UUID | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class WidgetUpdate(BaseModel):
    """Partial update for a widget."""

    widget_type: Literal["chart", "gauge", "stat_card", "status"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    sensor_id: uuid.UUID | None = None
    config: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    sort_order: int | None = None


class WidgetRead(BaseModel):
    """Widget response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dashboard_id: uuid.UUID
    widget_type: str
    title: str
    sensor_id: uuid.UUID | None = None
    config: dict[str, Any]
    layout: dict[str, Any]
    sort_order: int
    created_at: datetime


# ── Dashboards ──────────────────────────────────────────────────

class DashboardCreate(BaseModel):
    """Request body to create a dashboard."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool = False


class DashboardUpdate(BaseModel):
    """Partial update for a dashboard."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool | None = None


class DashboardRead(BaseModel):
    """Dashboard response (without widgets)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime
    widget_count: int = 0


class DashboardDetail(BaseModel):
    """Dashboard response with nested widgets."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime
    widgets: list[WidgetRead] = []
