"""Shared parsers for Redis-stream payloads."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from nodelens.schemas.events import TelemetryEvent

if TYPE_CHECKING:
    from collections.abc import Iterable


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


def partition_telemetry_batch(
    messages: Iterable[tuple[str, dict]],
    *,
    logger: logging.Logger | None = None,
) -> tuple[list[TelemetryEvent], list[str], list[str]]:
    """Split a stream batch into parsed events plus parseable / unparseable IDs.

    Used by both the ingestor and the alerts engine: parse what we can, log
    each malformed message, and return the IDs separately so the caller can
    ACK the bad ones immediately and ACK the good ones only after processing.
    """
    log = logger or logging.getLogger("nodelens.redis.parse")
    events: list[TelemetryEvent] = []
    good_ids: list[str] = []
    bad_ids: list[str] = []
    for msg_id, fields in messages:
        try:
            events.append(parse_telemetry_event(fields))
            good_ids.append(msg_id)
        except (KeyError, ValueError) as exc:
            log.warning("Dropping malformed message %s: %s", msg_id, exc)
            bad_ids.append(msg_id)
    return events, good_ids, bad_ids
