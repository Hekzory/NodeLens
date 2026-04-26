"""Threshold check used by both instant and aggregated rule paths."""

from __future__ import annotations

from nodelens.workers.alerts.conditions.base import compare


def fires(condition: str, value: float | None, threshold: float | None) -> bool:
    """Return True iff the (value, threshold) pair matches the condition.

    Both must be present and finite for the rule to fire.
    """
    if value is None or threshold is None:
        return False
    return compare(condition, value, threshold)
