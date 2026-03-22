"""Device plugin abstract class."""

from __future__ import annotations

from abc import abstractmethod

from nodelens.schemas.events import TelemetryEvent
from nodelens.sdk.base_plugin import BasePlugin


class DevicePlugin(BasePlugin):
    """Base class for device (telemetry-source) plugins.

    Subclasses that receive external data (e.g. MQTT messages) should implement
    ``on_message`` to normalise raw bytes into ``TelemetryEvent`` objects.

    Plugins that generate data internally (demo, simulator) may return an empty
    list from ``on_message`` and instead publish events directly in ``start()``.
    """

    @abstractmethod
    def on_message(self, raw_data: bytes) -> list[TelemetryEvent]:
        """Normalise raw incoming data into telemetry events."""
        ...
