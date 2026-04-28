"""DB-backed runtime configuration for NodeLens.

Public surface:
- ``REGISTRY`` — declarative metadata per setting (label, type, default,
  validation, ``requires_restart`` flag).
- ``runtime_settings`` — per-process singleton with TTL-cached reads and
  validated writes.
- ``SettingsValidationError`` — raised by ``runtime_settings.update`` when an
  input fails type/bounds/cross-field checks.

Defaults still come from ``nodelens.config.settings``. A row in the
``system_settings`` table overrides the corresponding default; missing rows
fall back to ``settings``.
"""

from nodelens.system_settings.registry import (
    GROUP_ORDER,
    REGISTRY,
    SettingDef,
    SettingGroup,
    ValueType,
    cross_field_invariants,
    iter_settings,
)
from nodelens.system_settings.service import (
    RuntimeSettings,
    SettingsValidationError,
    runtime_settings,
)

__all__ = [
    "REGISTRY",
    "GROUP_ORDER",
    "SettingDef",
    "SettingGroup",
    "ValueType",
    "RuntimeSettings",
    "SettingsValidationError",
    "iter_settings",
    "cross_field_invariants",
    "runtime_settings",
]
