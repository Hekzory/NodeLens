"""Rule evaluation — pure-ish: queries DB but no side-effects beyond reads."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from nodelens.db.models import AlertHistory, AlertRule, TelemetryRecord
from nodelens.workers.alerts.conditions.threshold import fires

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nodelens.schemas.events import TelemetryEvent

logger = logging.getLogger("nodelens.alerts.evaluator")

# Whitelist of aggregation function names → SQL aggregate. Never interpolate user input.
_AGG_FN = {
    "avg": func.avg,
    "min": func.min,
    "max": func.max,
    "sum": func.sum,
    "count": func.count,
}


@dataclass(frozen=True, slots=True)
class FireDecision:
    rule: AlertRule
    triggered_value: float | None
    message: str
    triggered_at: datetime


async def load_active_rules_for_sensor(
    session: AsyncSession, sensor_id: str
) -> list[AlertRule]:
    """Active rules attached to the given sensor."""
    stmt = select(AlertRule).where(
        AlertRule.sensor_id == sensor_id,
        AlertRule.is_active.is_(True),
    )
    return list((await session.execute(stmt)).scalars().all())


async def is_in_cooldown(
    session: AsyncSession, rule: AlertRule, now: datetime
) -> bool:
    """True iff the rule fired within the last ``cooldown_seconds``."""
    if rule.cooldown_seconds <= 0:
        return False
    stmt = select(func.max(AlertHistory.triggered_at)).where(
        AlertHistory.rule_id == rule.id
    )
    last = (await session.execute(stmt)).scalar()
    if last is None:
        return False
    return (now - last) < timedelta(seconds=rule.cooldown_seconds)


async def _aggregate_value(
    session: AsyncSession, rule: AlertRule, now: datetime
) -> float | None:
    """Run the rule's aggregation over its window. Returns None on no data."""
    agg_name = rule.aggregation or "avg"
    agg_fn = _AGG_FN.get(agg_name)
    if agg_fn is None:
        logger.warning("Unknown aggregation '%s' on rule %s — skipping", agg_name, rule.name)
        return None
    window_start = now - timedelta(seconds=rule.duration_seconds)
    stmt = select(agg_fn(TelemetryRecord.value_numeric)).where(
        TelemetryRecord.sensor_id == rule.sensor_id,
        TelemetryRecord.time >= window_start,
        TelemetryRecord.time <= now,
    )
    val = (await session.execute(stmt)).scalar()
    return float(val) if val is not None else None


async def _instant_decision(rule: AlertRule, event: TelemetryEvent, now: datetime) -> FireDecision | None:
    if not fires(rule.condition, event.value, rule.threshold):
        return None
    msg = f"{rule.name}: value {event.value} {rule.condition} threshold {rule.threshold}"
    return FireDecision(rule=rule, triggered_value=event.value, message=msg, triggered_at=now)


async def _aggregated_decision(
    session: AsyncSession, rule: AlertRule, now: datetime
) -> FireDecision | None:
    agg_val = await _aggregate_value(session, rule, now)
    if not fires(rule.condition, agg_val, rule.threshold):
        return None
    msg = (
        f"{rule.name}: {rule.aggregation}(value) over {rule.duration_seconds}s = "
        f"{agg_val} {rule.condition} threshold {rule.threshold}"
    )
    return FireDecision(rule=rule, triggered_value=agg_val, message=msg, triggered_at=now)


async def evaluate(
    session: AsyncSession, rule: AlertRule, event: TelemetryEvent
) -> FireDecision | None:
    """Evaluate a single rule against an incoming telemetry event."""
    now = datetime.now(UTC)

    if rule.condition == "no_data":
        # The event-driven path skips no_data; the periodic no_data_scanner
        # owns these rules. Emitting here would also be useless because the
        # event we're processing proves the sensor is *not* silent.
        return None
    if await is_in_cooldown(session, rule, now):
        return None
    if rule.rule_type == "instant":
        return await _instant_decision(rule, event, now)
    if rule.rule_type == "aggregated":
        return await _aggregated_decision(session, rule, now)

    logger.warning("Unknown rule_type '%s' on rule %s — skipping", rule.rule_type, rule.name)
    return None
