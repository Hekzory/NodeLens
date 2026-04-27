"""Alert rule & alert history endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens.api.deps import get_db
from nodelens.db.models import (
    AlertHistory,
    AlertRule,
    AlertRuleChannel,
    NotificationChannel,
    Plugin,
    Sensor,
)
from nodelens.schemas.alerts import (
    AlertHistoryRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
)
from nodelens.schemas.notifications import (
    NotificationChannelRead,
    RuleChannelsUpdate,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── Helpers ─────────────────────────────────────────────────────


async def _channel_ids_for_rule(db: AsyncSession, rule_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(AlertRuleChannel.channel_id).where(AlertRuleChannel.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def _channel_ids_by_rule(
    db: AsyncSession, rule_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    if not rule_ids:
        return {}
    stmt = select(AlertRuleChannel.rule_id, AlertRuleChannel.channel_id).where(
        AlertRuleChannel.rule_id.in_(rule_ids)
    )
    out: dict[uuid.UUID, list[uuid.UUID]] = {rid: [] for rid in rule_ids}
    for rid, cid in (await db.execute(stmt)).all():
        out.setdefault(rid, []).append(cid)
    return out


async def _rule_to_read(db: AsyncSession, rule: AlertRule) -> AlertRuleRead:
    data = AlertRuleRead.model_validate(rule)
    data.channel_ids = await _channel_ids_for_rule(db, rule.id)
    return data


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

    rules = list((await db.execute(stmt)).scalars().all())
    by_rule = await _channel_ids_by_rule(db, [r.id for r in rules])
    out: list[AlertRuleRead] = []
    for r in rules:
        data = AlertRuleRead.model_validate(r)
        data.channel_ids = by_rule.get(r.id, [])
        out.append(data)
    return out


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
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Alert rule with this name already exists") from exc
    await db.refresh(rule)
    return await _rule_to_read(db, rule)


@router.get("/rules/{rule_id}", response_model=AlertRuleRead)
async def get_alert_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single alert rule."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return await _rule_to_read(db, rule)


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

    # Validate the merged final state for no_data invariants. Pydantic
    # cannot do this on a partial schema since it only sees the patch.
    if rule.condition == "no_data":
        if rule.duration_seconds is None or rule.duration_seconds <= 0:
            raise HTTPException(
                status_code=400,
                detail="no_data rules require duration_seconds > 0",
            )
        if rule.aggregation is not None:
            raise HTTPException(
                status_code=400,
                detail="aggregation is not allowed for no_data rules",
            )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Alert rule with this name already exists") from exc
    await db.refresh(rule)
    return await _rule_to_read(db, rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_alert_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an alert rule and its history."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await db.delete(rule)
    await db.commit()


# ── Rule ↔ Channel Links ───────────────────────────────────────


@router.get("/rules/{rule_id}/channels", response_model=list[NotificationChannelRead])
async def list_rule_channels(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List channels linked to a rule."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    stmt = (
        select(NotificationChannel, Plugin)
        .join(AlertRuleChannel, AlertRuleChannel.channel_id == NotificationChannel.id)
        .join(Plugin, Plugin.id == NotificationChannel.plugin_id)
        .where(AlertRuleChannel.rule_id == rule_id)
        .order_by(NotificationChannel.name)
    )
    rows = (await db.execute(stmt)).all()
    out: list[NotificationChannelRead] = []
    for ch, plugin in rows:
        data = NotificationChannelRead.model_validate(ch)
        data.plugin_module_name = plugin.module_name if plugin else None
        out.append(data)
    return out


@router.put("/rules/{rule_id}/channels", response_model=AlertRuleRead)
async def set_rule_channels(
    rule_id: uuid.UUID,
    body: RuleChannelsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Replace the rule's set of linked channels with the given list (idempotent)."""
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    desired = set(body.channel_ids)
    if desired:
        existing_channels = (
            await db.execute(
                select(NotificationChannel.id).where(NotificationChannel.id.in_(desired))
            )
        ).scalars().all()
        missing = desired - set(existing_channels)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown channel id(s): {', '.join(str(m) for m in sorted(missing))}",
            )

    current = set(
        (
            await db.execute(
                select(AlertRuleChannel.channel_id).where(AlertRuleChannel.rule_id == rule_id)
            )
        ).scalars().all()
    )

    to_add = desired - current
    to_remove = current - desired

    for cid in to_add:
        db.add(AlertRuleChannel(rule_id=rule_id, channel_id=cid))
    if to_remove:
        for cid in to_remove:
            link = await db.get(AlertRuleChannel, (rule_id, cid))
            if link is not None:
                await db.delete(link)

    await db.commit()
    await db.refresh(rule)
    return await _rule_to_read(db, rule)


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
        .options(selectinload(AlertHistory.rule))
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
        data.rule_name = h.rule.name if h.rule else None
        results.append(data)
    return results


@router.post("/history/{history_id}/acknowledge", response_model=AlertHistoryRead)
async def acknowledge_alert(
    history_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a fired alert."""
    stmt = (
        select(AlertHistory)
        .where(AlertHistory.id == history_id)
        .options(selectinload(AlertHistory.rule))
    )
    history = (await db.execute(stmt)).scalar_one_or_none()
    if history is None:
        raise HTTPException(status_code=404, detail="Alert history record not found")
    if history.acknowledged_at is not None:
        raise HTTPException(status_code=400, detail="Alert already acknowledged")

    history.acknowledged_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(history)

    data = AlertHistoryRead.model_validate(history)
    data.rule_name = history.rule.name if history.rule else None
    return data
