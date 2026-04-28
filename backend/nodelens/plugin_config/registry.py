"""Per-plugin configuration field metadata.

Each plugin declares its own ``config_schema:`` block in ``manifest.yaml``;
that YAML list is parsed into a list of :class:`PluginConfigField` instances
on plugin discovery and persisted to ``plugins.config_schema`` (JSONB) by the
plugin worker. The API and the subprocess runner both read the schema back
out of the DB — the API container has no access to ``PLUGINS_DIR``.

Mirrors :mod:`nodelens.system_settings.registry` but scoped per-plugin and
without cross-field invariants. Adds a ``secret`` value type that behaves
like ``string`` at storage time but is masked in API responses and rendered
as a password input in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ValueType = Literal["int", "float", "bool", "string", "secret"]
_ALLOWED_VALUE_TYPES: frozenset[str] = frozenset(
    {"int", "float", "bool", "string", "secret"}
)


@dataclass(frozen=True, slots=True)
class PluginConfigField:
    key: str
    label: str
    group: str
    value_type: ValueType
    default: Any
    help: str = ""
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    requires_restart: bool = False

    def coerce(self, raw: Any) -> Any:
        """Convert JSON-decoded raw → typed Python value."""
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
        if self.value_type in ("string", "secret"):
            if isinstance(raw, str):
                return raw
            raise ValueError(f"{self.key} must be a string")
        raise AssertionError(f"unknown value_type {self.value_type!r}")

    def validate(self, value: Any) -> None:
        """Enforce min/max for numeric fields. Raises ``ValueError`` on miss."""
        if self.value_type in ("int", "float"):
            if self.min is not None and value < self.min:
                raise ValueError(f"{self.key} must be >= {self.min}")
            if self.max is not None and value > self.max:
                raise ValueError(f"{self.key} must be <= {self.max}")


def parse_schema(raw: Any) -> list[PluginConfigField]:
    """Parse a manifest's ``config_schema`` block.

    Validates structure, types, and uniqueness of ``key``s. Raises
    ``ValueError`` with a path-like prefix (``config_schema[idx]``) so the
    plugin loader's warning is precise enough to debug.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("config_schema: must be a list")

    fields: list[PluginConfigField] = []
    seen_keys: set[str] = set()
    for idx, entry in enumerate(raw):
        prefix = f"config_schema[{idx}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{prefix}: must be a mapping")
        for required in ("key", "label", "value_type"):
            if required not in entry:
                raise ValueError(f"{prefix}: missing {required!r}")

        key = entry["key"]
        if not isinstance(key, str) or not key:
            raise ValueError(f"{prefix}: 'key' must be a non-empty string")
        if key in seen_keys:
            raise ValueError(f"{prefix}: duplicate key {key!r}")
        seen_keys.add(key)

        value_type = entry["value_type"]
        if value_type not in _ALLOWED_VALUE_TYPES:
            raise ValueError(
                f"{prefix}: unknown value_type {value_type!r} "
                f"(allowed: int, float, bool, string, secret)"
            )

        label = entry["label"]
        if not isinstance(label, str):
            raise ValueError(f"{prefix}: 'label' must be a string")

        default = entry.get("default")
        if default is None:
            default = _zero_default(value_type)

        field = PluginConfigField(
            key=key,
            label=label,
            group=str(entry.get("group") or "general"),
            value_type=value_type,  # type: ignore[arg-type]
            default=default,
            help=str(entry.get("help") or ""),
            unit=(entry.get("unit") or None),
            min=_optional_float(entry.get("min"), prefix, "min"),
            max=_optional_float(entry.get("max"), prefix, "max"),
            requires_restart=bool(entry.get("requires_restart", False)),
        )
        # Verify the declared default actually round-trips through coerce so
        # we surface schema bugs eagerly rather than at first read.
        try:
            coerced_default = field.coerce(field.default)
            field.validate(coerced_default)
        except ValueError as exc:
            raise ValueError(f"{prefix}: invalid default — {exc}") from None
        fields.append(field)

    return fields


def _zero_default(value_type: str) -> Any:
    if value_type == "int":
        return 0
    if value_type == "float":
        return 0.0
    if value_type == "bool":
        return False
    return ""  # string / secret


def _optional_float(raw: Any, prefix: str, name: str) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{prefix}: {name!r} must be a number")
    return float(raw)


def schema_to_jsonable(schema: list[PluginConfigField]) -> list[dict[str, Any]]:
    """Round-trip a parsed schema back into the JSON-compatible list form.

    Used by the supervisor when persisting to ``plugins.config_schema``. The
    DB column stores the canonicalized form so consumers don't have to re-
    parse string→float coercion edge cases.
    """
    return [
        {
            "key": f.key,
            "label": f.label,
            "group": f.group,
            "value_type": f.value_type,
            "default": f.default,
            "help": f.help,
            "unit": f.unit,
            "min": f.min,
            "max": f.max,
            "requires_restart": f.requires_restart,
        }
        for f in schema
    ]
