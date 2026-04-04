"""Dashboard & widget endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nodelens.api.deps import get_db
from nodelens.db.models import Dashboard, DashboardWidget, Sensor
from nodelens.schemas.dashboards import (
    DashboardCreate,
    DashboardUpdate,
    DashboardRead,
    DashboardDetail,
    WidgetCreate,
    WidgetUpdate,
    WidgetRead,
)

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


# ── Dashboards ──────────────────────────────────────────────────


@router.get("", response_model=list[DashboardRead])
async def list_dashboards(db: AsyncSession = Depends(get_db)):
    """List all dashboards with widget counts."""
    stmt = (
        select(
            Dashboard,
            func.count(DashboardWidget.id).label("widget_count"),
        )
        .outerjoin(DashboardWidget, DashboardWidget.dashboard_id == Dashboard.id)
        .group_by(Dashboard.id)
        .order_by(Dashboard.created_at)
    )
    rows = (await db.execute(stmt)).all()
    results = []
    for dashboard, widget_count in rows:
        data = DashboardRead.model_validate(dashboard)
        data.widget_count = widget_count
        results.append(data)
    return results


@router.post("", response_model=DashboardRead, status_code=201)
async def create_dashboard(
    body: DashboardCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new dashboard."""
    # If this is set as default, unset any existing default
    if body.is_default:
        await _unset_default_dashboards(db)

    dashboard = Dashboard(**body.model_dump())
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)

    data = DashboardRead.model_validate(dashboard)
    data.widget_count = 0
    return data


@router.get("/{dashboard_id}", response_model=DashboardDetail)
async def get_dashboard(
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard detail with all widgets."""
    stmt = (
        select(Dashboard)
        .where(Dashboard.id == dashboard_id)
        .options(selectinload(Dashboard.widgets))
    )
    dashboard = (await db.execute(stmt)).scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return DashboardDetail(
        id=dashboard.id,
        name=dashboard.name,
        description=dashboard.description,
        is_default=dashboard.is_default,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
        widgets=[WidgetRead.model_validate(w) for w in dashboard.widgets],
    )


@router.patch("/{dashboard_id}", response_model=DashboardRead)
async def update_dashboard(
    dashboard_id: uuid.UUID,
    body: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update dashboard metadata."""
    dashboard = await db.get(Dashboard, dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    update_data = body.model_dump(exclude_unset=True)

    # Handle default toggle
    if update_data.get("is_default"):
        await _unset_default_dashboards(db)

    for field, value in update_data.items():
        setattr(dashboard, field, value)

    await db.commit()
    await db.refresh(dashboard)

    # Get widget count
    count_stmt = (
        select(func.count(DashboardWidget.id))
        .where(DashboardWidget.dashboard_id == dashboard_id)
    )
    widget_count = (await db.execute(count_stmt)).scalar() or 0

    data = DashboardRead.model_validate(dashboard)
    data.widget_count = widget_count
    return data


@router.delete("/{dashboard_id}", status_code=204)
async def delete_dashboard(
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a dashboard and all its widgets."""
    dashboard = await db.get(Dashboard, dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    await db.delete(dashboard)
    await db.commit()


# ── Widgets ─────────────────────────────────────────────────────


@router.post("/{dashboard_id}/widgets", response_model=WidgetRead, status_code=201)
async def create_widget(
    dashboard_id: uuid.UUID,
    body: WidgetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a widget to a dashboard."""
    dashboard = await db.get(Dashboard, dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Validate sensor if provided
    if body.sensor_id is not None:
        sensor = await db.get(Sensor, body.sensor_id)
        if sensor is None:
            raise HTTPException(status_code=400, detail="Sensor not found")

    widget = DashboardWidget(dashboard_id=dashboard_id, **body.model_dump())
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return WidgetRead.model_validate(widget)


@router.patch("/{dashboard_id}/widgets/{widget_id}", response_model=WidgetRead)
async def update_widget(
    dashboard_id: uuid.UUID,
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a widget on a dashboard."""
    widget = await _get_widget(db, dashboard_id, widget_id)

    update_data = body.model_dump(exclude_unset=True)

    if "sensor_id" in update_data and update_data["sensor_id"] is not None:
        sensor = await db.get(Sensor, update_data["sensor_id"])
        if sensor is None:
            raise HTTPException(status_code=400, detail="Sensor not found")

    for field, value in update_data.items():
        setattr(widget, field, value)

    await db.commit()
    await db.refresh(widget)
    return WidgetRead.model_validate(widget)


@router.delete("/{dashboard_id}/widgets/{widget_id}", status_code=204)
async def delete_widget(
    dashboard_id: uuid.UUID,
    widget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a widget from a dashboard."""
    widget = await _get_widget(db, dashboard_id, widget_id)
    await db.delete(widget)
    await db.commit()


# ── Helpers ─────────────────────────────────────────────────────


async def _get_widget(
    db: AsyncSession, dashboard_id: uuid.UUID, widget_id: uuid.UUID
) -> DashboardWidget:
    """Fetch a widget and verify it belongs to the given dashboard."""
    widget = await db.get(DashboardWidget, widget_id)
    if widget is None or widget.dashboard_id != dashboard_id:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget


async def _unset_default_dashboards(db: AsyncSession) -> None:
    """Clear is_default on all dashboards (before setting a new default)."""
    stmt = select(Dashboard).where(Dashboard.is_default.is_(True))
    defaults = (await db.execute(stmt)).scalars().all()
    for d in defaults:
        d.is_default = False
