"""baseline

Captures the schema as it existed before Alembic was wired in: plugins,
devices, sensors, telemetry (TimescaleDB hypertable), alert_rules,
alert_history, notification_channels, alert_rule_channels, dashboards,
dashboard_widgets.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_type", sa.String(), nullable=False),
        sa.Column("module_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module_name"),
    )

    op.create_table(
        "dashboards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_plugin_id", "devices", ["plugin_id"])

    op.create_table(
        "sensors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sensors_device_id", "sensors", ["device_id"])

    op.create_table(
        "telemetry",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"]),
        sa.PrimaryKeyConstraint("time", "sensor_id"),
    )
    # TimescaleDB-specific: convert the plain table into a hypertable. Autogen
    # cannot infer this — it must be explicit.
    op.execute(
        "SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);"
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_type", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("aggregation", sa.String(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_alert_rules_sensor_id", "alert_rules", ["sensor_id"])

    op.create_table(
        "alert_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_value", sa.Float(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_history_rule_id", "alert_history", ["rule_id"])

    op.create_table(
        "notification_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_notification_channels_plugin_id", "notification_channels", ["plugin_id"]
    )

    op.create_table(
        "alert_rule_channels",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["notification_channels.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("rule_id", "channel_id"),
    )
    op.create_index(
        "ix_alert_rule_channels_rule_id", "alert_rule_channels", ["rule_id"]
    )

    op.create_table(
        "dashboard_widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dashboard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("widget_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dashboard_id"], ["dashboards.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_widgets_dashboard_id", "dashboard_widgets", ["dashboard_id"]
    )
    op.create_index(
        "ix_dashboard_widgets_sensor_id", "dashboard_widgets", ["sensor_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_widgets_sensor_id", table_name="dashboard_widgets")
    op.drop_index("ix_dashboard_widgets_dashboard_id", table_name="dashboard_widgets")
    op.drop_table("dashboard_widgets")

    op.drop_index("ix_alert_rule_channels_rule_id", table_name="alert_rule_channels")
    op.drop_table("alert_rule_channels")

    op.drop_index(
        "ix_notification_channels_plugin_id", table_name="notification_channels"
    )
    op.drop_table("notification_channels")

    op.drop_index("ix_alert_history_rule_id", table_name="alert_history")
    op.drop_table("alert_history")

    op.drop_index("ix_alert_rules_sensor_id", table_name="alert_rules")
    op.drop_table("alert_rules")

    op.drop_table("telemetry")

    op.drop_index("ix_sensors_device_id", table_name="sensors")
    op.drop_table("sensors")

    op.drop_index("ix_devices_plugin_id", table_name="devices")
    op.drop_table("devices")

    op.drop_table("dashboards")
    op.drop_table("plugins")
