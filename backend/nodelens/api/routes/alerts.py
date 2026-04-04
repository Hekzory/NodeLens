"""Alert rule & alert history endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from nodelens.api.deps import get_db
from nodelens.db.models import AlertHistory, AlertRule, Sensor
from nodelens.schemas.alerts import (
    AlertHistoryRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── Alert Rules ─────────────────────────────────────────────────


@router.get("/rules", response_model=list[AlertRuleRead])
async def list_alert_rules(
    is_active: bool | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List all alert rules."""
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(AlertRule.is_active == is_active)
    if severity is not None:
        stmt = stmt.where(AlertRule.severity == severity)

    rules = (await db.execute(stmt)).scalars().all()
    return [AlertRuleRead.model_validate(r) for r in rules]


@router.post("/rules", response_model=AlertRuleRead, status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert rule."""
    # Validate sensor exists
    sensor = await db.get(Sensor, body.sensor_id)
    if sensor is None:
        raise HTTPException(status_code=400, detail="Sensor not found")

    # Validate: aggregated rules must have aggregation + duration > 0
    if body.rule_type == "aggregated":
        if not body.aggregation:
            raise HTTPException(
                status_code=400,
                detail="Aggregated rules require an 'aggregation' function (avg, min, max, sum, count)",
            )
        if body.duration_seconds <= 0:
            raise HTTPException(
                status_code=400,
                detail="Aggregated rules require 'duration_seconds' > 0",
            )

    # no_data rules don't need a threshold
    if body.condition != "no_data" and body.threshold is None:
        raise HTTPException(status_code=400, detail="Threshold is required for this condition type")

    rule = AlertRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return AlertRuleRead.model_validate(rule)


@router.get("/rules/{rule_id}", response_model=AlertRuleRead)
async def get_alert_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single alert rule."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRuleRead.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=AlertRuleRead)
async def update_alert_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an alert rule."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    update_data = body.model_dump(exclude_unset=True)

    # If sensor_id is being changed, verify the new sensor exists
    if "sensor_id" in update_data:
        sensor = await db.get(Sensor, update_data["sensor_id"])
        if sensor is None:
            raise HTTPException(status_code=400, detail="Sensor not found")

    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return AlertRuleRead.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_alert_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an alert rule and its history."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await db.delete(rule)
    await db.commit()


# ── Alert History ───────────────────────────────────────────────


@router.get("/history", response_model=list[AlertHistoryRead])
async def list_alert_history(
    rule_id: uuid.UUID | None = Query(default=None),
    severity: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List alert history with pagination and filters."""
    stmt = (
        select(AlertHistory)
        .join(AlertRule)
        .order_by(desc(AlertHistory.triggered_at))
    )

    if rule_id is not None:
        stmt = stmt.where(AlertHistory.rule_id == rule_id)
    if severity is not None:
        stmt = stmt.where(AlertRule.severity == severity)
    if acknowledged is True:
        stmt = stmt.where(AlertHistory.acknowledged_at.is_not(None))
    elif acknowledged is False:
        stmt = stmt.where(AlertHistory.acknowledged_at.is_(None))
    if start is not None:
        stmt = stmt.where(AlertHistory.triggered_at >= start)
    if end is not None:
        stmt = stmt.where(AlertHistory.triggered_at <= end)

    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    results = []
    for h in rows:
        data = AlertHistoryRead.model_validate(h)
        # Eagerly load rule name
        rule = await db.get(AlertRule, h.rule_id)
        data.rule_name = rule.name if rule else None
        results.append(data)
    return results


@router.post("/history/{history_id}/acknowledge", response_model=AlertHistoryRead)
async def acknowledge_alert(
    history_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a fired alert."""
    history = await db.get(AlertHistory, history_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Alert history record not found")
    if history.acknowledged_at is not None:
        raise HTTPException(status_code=400, detail="Alert already acknowledged")

    history.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(history)

    rule = await db.get(AlertRule, history.rule_id)
    data = AlertHistoryRead.model_validate(history)
    data.rule_name = rule.name if rule else None
    return data
