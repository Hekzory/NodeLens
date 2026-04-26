"""Shared parsers for Redis-stream payloads."""

from __future__ import annotations

from datetime import datetime

from nodelens.schemas.events import TelemetryEvent


def parse_telemetry_event(fields: dict) -> TelemetryEvent:
    """Decode a TelemetryEvent from raw stream fields.

    Raises KeyError or ValueError on malformed input.
    """
    return TelemetryEvent(
        device_id=fields["device_id"],
        sensor_id=fields["sensor_id"],
        value=float(fields["value"]),
        timestamp=datetime.fromisoformat(fields["timestamp"]),
    )
