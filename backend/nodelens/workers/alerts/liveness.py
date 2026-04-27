"""Shared liveness state between the alert engine and the no_data scanner.

Single-threaded asyncio guarantees safe access to module-level state without locks.
The state lives at module scope because the engine and scanner run as concurrent
tasks in the same process; importing from a small dedicated module avoids cyclic
imports and keeps the surface easy to reset/inspect in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import timedelta

# Set by run_no_data_scanner() on its first tick. Reset only by reset_for_tests().
_scanner_start_time = None  # type: ignore[var-annotated]

# Set by the engine each time it processes a non-empty telemetry batch.
_last_event_processed_at = None  # type: ignore[var-annotated]


def mark_scanner_started(now) -> None:
    """Record scanner first-tick time. Idempotent — keeps the earliest value."""
    global _scanner_start_time
    if _scanner_start_time is None:
        _scanner_start_time = now


def mark_event_processed(now) -> None:
    """Record that the engine just processed at least one telemetry event."""
    global _last_event_processed_at
    _last_event_processed_at = now


def scanner_uptime(now) -> timedelta | None:
    if _scanner_start_time is None:
        return None
    return now - _scanner_start_time


def time_since_last_event(now) -> timedelta | None:
    if _last_event_processed_at is None:
        return None
    return now - _last_event_processed_at


def reset_for_tests() -> None:
    global _scanner_start_time, _last_event_processed_at
    _scanner_start_time = None
    _last_event_processed_at = None
