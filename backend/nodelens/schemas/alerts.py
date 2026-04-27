"""Pydantic schemas for alert rule and alert history API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── Alert Rules ─────────────────────────────────────────────────


class AlertRuleCreate(BaseModel):
    """Request body to create an alert rule."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    sensor_id: uuid.UUID
    rule_type: Literal["instant", "aggregated"] = "instant"
    condition: Literal["gt", "lt", "gte", "lte", "eq", "neq", "no_data"]
    threshold: float | None = None
    aggregation: Literal["avg", "min", "max", "sum", "count"] | None = None
    duration_seconds: int = Field(default=0, ge=0)
    cooldown_seconds: int = Field(default=300, ge=0)
    severity: Literal["info", "warning", "critical"] = "warning"
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_no_data_invariants(self) -> "AlertRuleCreate":
        if self.condition == "no_data":
            if self.duration_seconds <= 0:
                raise ValueError(
                    "no_data rules require duration_seconds > 0 (the silence window)"
                )
            if self.aggregation is not None:
                raise ValueError("aggregation is not allowed for no_data rules")
        return self


class AlertRuleUpdate(BaseModel):
    """Partial update for an alert rule."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    sensor_id: uuid.UUID | None = None
    rule_type: Literal["instant", "aggregated"] | None = None
    condition: Literal["gt", "lt", "gte", "lte", "eq", "neq", "no_data"] | None = None
    threshold: float | None = None
    aggregation: Literal["avg", "min", "max", "sum", "count"] | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    cooldown_seconds: int | None = Field(default=None, ge=0)
    severity: Literal["info", "warning", "critical"] | None = None
    is_active: bool | None = None


class AlertRuleRead(BaseModel):
    """Alert rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    sensor_id: uuid.UUID
    rule_type: str
    condition: str
    threshold: float | None = None
    aggregation: str | None = None
    duration_seconds: int
    cooldown_seconds: int
    severity: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    channel_ids: list[uuid.UUID] = Field(default_factory=list)


# ── Alert History ───────────────────────────────────────────────

class AlertHistoryRead(BaseModel):
    """Fired alert record response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str | None = None
    triggered_value: float | None = None
    message: str
    triggered_at: datetime
    acknowledged_at: datetime | None = None
