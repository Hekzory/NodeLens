"""Unit tests for the alerts liveness module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nodelens.workers.alerts import liveness


@pytest.fixture(autouse=True)
def _reset():
    liveness.reset_for_tests()
    yield
    liveness.reset_for_tests()


def test_accessors_return_none_before_any_marks():
    now = datetime.now(UTC)
    assert liveness.scanner_uptime(now) is None
    assert liveness.time_since_last_event(now) is None


def test_mark_scanner_started_records_first_call():
    t0 = datetime.now(UTC)
    liveness.mark_scanner_started(t0)
    later = t0 + timedelta(seconds=10)
    assert liveness.scanner_uptime(later) == timedelta(seconds=10)


def test_mark_scanner_started_is_idempotent():
    t0 = datetime.now(UTC)
    t1 = t0 + timedelta(seconds=30)
    liveness.mark_scanner_started(t0)
    liveness.mark_scanner_started(t1)  # second call must not overwrite
    later = t0 + timedelta(seconds=60)
    assert liveness.scanner_uptime(later) == timedelta(seconds=60)


def test_mark_event_processed_overwrites():
    t0 = datetime.now(UTC)
    t1 = t0 + timedelta(seconds=10)
    liveness.mark_event_processed(t0)
    liveness.mark_event_processed(t1)
    later = t0 + timedelta(seconds=15)
    assert liveness.time_since_last_event(later) == timedelta(seconds=5)
