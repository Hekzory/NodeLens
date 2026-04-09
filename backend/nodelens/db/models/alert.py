import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nodelens.db.base import Base


class AlertRule(Base):
    """User-defined alert condition on a sensor's telemetry."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sensors.id"), nullable=False, index=True
    )
    # "instant" — single-value realtime check; "aggregated" — check over a time window
    rule_type: Mapped[str] = mapped_column(String, nullable=False, default="instant")
    # Condition operator: gt, lt, gte, lte, eq, neq, no_data
    condition: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    # For aggregated rules: the aggregation function (avg, min, max, sum, count)
    aggregation: Mapped[str | None] = mapped_column(String, nullable=True)
    # Time window in seconds — 0 means instant / realtime
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Minimum seconds between re-triggers
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="warning")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sensor: Mapped["Sensor"] = relationship()  # noqa: F821
    history: Mapped[list["AlertHistory"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class AlertHistory(Base):
    """Record of a fired alert."""

    __tablename__ = "alert_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rule: Mapped["AlertRule"] = relationship(back_populates="history")
