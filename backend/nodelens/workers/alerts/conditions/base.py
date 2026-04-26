"""Operator dispatch table for alert rule conditions."""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

OPS: dict[str, Callable[[float, float], bool]] = {
    "gt": operator.gt,
    "lt": operator.lt,
    "gte": operator.ge,
    "lte": operator.le,
    "eq": operator.eq,
    "neq": operator.ne,
}


def compare(condition: str, value: float, threshold: float) -> bool:
    """Apply ``condition`` to (value, threshold). Returns False for unknown ops."""
    op = OPS.get(condition)
    if op is None:
        return False
    return op(value, threshold)
