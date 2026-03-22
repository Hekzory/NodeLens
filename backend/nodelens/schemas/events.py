from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """Canonical telemetry event — the contract between publishers and consumers.

    Both ``device_id`` and ``sensor_id`` are transmitted as strings.
    The ingestor casts ``sensor_id`` to UUID before writing.
    """

    device_id: str
    sensor_id: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class AlertMessage:
    """Alert payload delivered to integration plugins."""

    rule_name: str
    device_name: str
    triggered_value: float
    message: str
    triggered_at: datetime


# ── Registration events ─────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegisterPluginEvent:
    """Sent by a plugin on startup to register itself in the DB."""

    plugin_id: str
    plugin_type: str
    module_name: str
    display_name: str
    version: str


@dataclass(frozen=True, slots=True)
class RegisterDeviceEvent:
    """Sent by a plugin to register a device it manages."""

    device_id: str
    plugin_id: str
    external_id: str
    name: str
    location: str = ""


@dataclass(frozen=True, slots=True)
class RegisterSensorEvent:
    """Sent by a plugin to register a sensor on one of its devices."""

    sensor_id: str
    device_id: str
    key: str
    name: str
    unit: str = ""
    value_type: str = "numeric"
