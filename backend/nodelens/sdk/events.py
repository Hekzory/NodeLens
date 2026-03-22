"""Re-exports event dataclasses so plugin authors can import from the SDK."""

from nodelens.schemas.events import (
    AlertMessage,
    RegisterDeviceEvent,
    RegisterPluginEvent,
    RegisterSensorEvent,
    TelemetryEvent,
)

__all__ = [
    "TelemetryEvent",
    "AlertMessage",
    "RegisterPluginEvent",
    "RegisterDeviceEvent",
    "RegisterSensorEvent",
]
