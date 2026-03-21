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
