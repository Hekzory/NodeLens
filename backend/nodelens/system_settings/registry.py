"""Declarative metadata for every DB-backed system setting.

Single source of truth for each tunable: label, group, type, default (sourced
from `nodelens.config.settings`), unit, validation bounds, and whether
applying a change requires a service restart. The DB only stores user-set
values (`system_settings.key/value`); everything else lives here so that
neither the operator nor the frontend has to define it.

A change here may require an app code update at the call site that consumes
the new key.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from nodelens.config import settings

ValueType = Literal["int", "float", "bool", "string"]
SettingGroup = Literal["storage", "alerts", "devices", "ui"]

GROUP_ORDER: tuple[SettingGroup, ...] = ("storage", "alerts", "devices", "ui")


@dataclass(frozen=True, slots=True)
class SettingDef:
    key: str
    label: str
    group: SettingGroup
    value_type: ValueType
    default: Any
    help: str
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    requires_restart: bool = False
    affects_services: tuple[str, ...] = ()  # human-readable, shown in toast

    def coerce(self, raw: Any) -> Any:
        """Convert JSON-decoded raw → typed Python value.

        Handles ``int``/``float`` getting JSON-decoded as the wrong number
        type, and surfaces a clear ``ValueError`` on bool/string mismatches.
        """
        if self.value_type == "int":
            if isinstance(raw, bool):
                raise ValueError(f"{self.key} must be an integer, got bool")
            if isinstance(raw, int):
                return raw
            if isinstance(raw, float) and raw.is_integer():
                return int(raw)
            raise ValueError(f"{self.key} must be an integer")
        if self.value_type == "float":
            if isinstance(raw, bool):
                raise ValueError(f"{self.key} must be a number, got bool")
            if isinstance(raw, (int, float)):
                return float(raw)
            raise ValueError(f"{self.key} must be a number")
        if self.value_type == "bool":
            if isinstance(raw, bool):
                return raw
            raise ValueError(f"{self.key} must be a boolean")
        if self.value_type == "string":
            if isinstance(raw, str):
                return raw
            raise ValueError(f"{self.key} must be a string")
        raise AssertionError(f"unknown value_type {self.value_type!r}")

    def validate(self, value: Any) -> None:
        """Enforce min/max for numeric settings. Raises ``ValueError`` on miss."""
        if self.value_type in ("int", "float"):
            if self.min is not None and value < self.min:
                raise ValueError(f"{self.key} must be >= {self.min}")
            if self.max is not None and value > self.max:
                raise ValueError(f"{self.key} must be <= {self.max}")


REGISTRY: dict[str, SettingDef] = {
    "retention_days": SettingDef(
        key="retention_days",
        label="Telemetry retention",
        group="storage",
        value_type="int",
        default=settings.RETENTION_DAYS,
        unit="days",
        min=1,
        max=10_000,
        requires_restart=True,
        affects_services=("ingestor",),
        help="Drop telemetry chunks older than this many days. Applied at "
        "ingestor startup via TimescaleDB retention policy.",
    ),
    "compression_after_days": SettingDef(
        key="compression_after_days",
        label="Compress after",
        group="storage",
        value_type="int",
        default=settings.COMPRESSION_AFTER_DAYS,
        unit="days",
        min=1,
        max=10_000,
        requires_restart=True,
        affects_services=("ingestor",),
        help="Compress telemetry chunks older than this many days. Must be "
        "less than retention.",
    ),
    "disk_budget_gb": SettingDef(
        key="disk_budget_gb",
        label="Disk budget",
        group="storage",
        value_type="int",
        default=settings.DISK_BUDGET_GB,
        unit="GB",
        min=1,
        max=100_000,
        requires_restart=False,
        help="Hard upper bound on telemetry on-disk size. The ingestor drops "
        "the oldest chunks when this is exceeded; takes effect on the next "
        "enforcement tick.",
    ),
    "retention_check_interval_seconds": SettingDef(
        key="retention_check_interval_seconds",
        label="Disk-budget check interval",
        group="storage",
        value_type="int",
        default=settings.RETENTION_CHECK_INTERVAL_SECONDS,
        unit="seconds",
        min=10,
        max=86_400,
        requires_restart=True,
        affects_services=("ingestor",),
        help="How often the ingestor checks the on-disk telemetry size against "
        "the disk budget.",
    ),
    "no_data_scan_interval_seconds": SettingDef(
        key="no_data_scan_interval_seconds",
        label="No-data scan interval",
        group="alerts",
        value_type="int",
        default=settings.NO_DATA_SCAN_INTERVAL_SECONDS,
        unit="seconds",
        min=1,
        max=3600,
        requires_restart=True,
        affects_services=("alerts",),
        help="How often the alerts worker scans for sensors that have stopped "
        "reporting (used by `condition=no_data` rules).",
    ),
    "online_threshold_minutes": SettingDef(
        key="online_threshold_minutes",
        label="Device online threshold",
        group="devices",
        value_type="int",
        default=settings.ONLINE_THRESHOLD_MINUTES,
        unit="minutes",
        min=1,
        max=10_080,
        requires_restart=False,
        help="A device is considered online when its last telemetry arrived "
        "within this window. Applies on every devices API request.",
    ),
    "frontend_polling_interval_seconds": SettingDef(
        key="frontend_polling_interval_seconds",
        label="Dashboard poll interval",
        group="ui",
        value_type="int",
        default=settings.FRONTEND_POLLING_INTERVAL_SECONDS,
        unit="seconds",
        min=2,
        max=600,
        requires_restart=False,
        help="How often the dashboard polls the API. The frontend updates its "
        "TanStack Query default on save; existing observers pick up the new "
        "cadence on their next refetch tick.",
    ),
}


def iter_settings() -> Iterator[SettingDef]:
    """Iterate registry in deterministic group → key order (stable for UI)."""
    by_group: dict[SettingGroup, list[SettingDef]] = {g: [] for g in GROUP_ORDER}
    for s in REGISTRY.values():
        by_group[s.group].append(s)
    for g in GROUP_ORDER:
        for s in sorted(by_group[g], key=lambda x: x.key):
            yield s


def cross_field_invariants(values: dict[str, Any]) -> None:
    """Cross-field validation. Raises ``ValueError`` with a single human message.

    Mirrors `Settings._compression_before_retention` from `config.py`.
    """
    if "retention_days" in values or "compression_after_days" in values:
        retention = values.get("retention_days", REGISTRY["retention_days"].default)
        compression = values.get(
            "compression_after_days", REGISTRY["compression_after_days"].default
        )
        if compression >= retention:
            raise ValueError(
                "compression_after_days must be < retention_days — otherwise "
                "chunks are dropped before they ever get compressed."
            )
