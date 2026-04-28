"""Per-plugin configuration — registry types + service layer.

Public surface:
- :class:`PluginConfigField` — one field's metadata (key, label, type,
  default, validation bounds).
- :func:`parse_schema` — validate a manifest's ``config_schema`` list.
- :class:`PluginConfigValidationError` — raised by :func:`update` when an
  input fails type/bounds checks.
- :func:`load`, :func:`effective_values`, :func:`update`, :func:`reset` —
  the read/write API used by the routes layer.
"""

from nodelens.plugin_config.registry import (
    PluginConfigField,
    ValueType,
    parse_schema,
    schema_to_jsonable,
)
from nodelens.plugin_config.service import (
    PluginConfigValidationError,
    effective_values,
    load,
    reset,
    update,
)

__all__ = [
    "PluginConfigField",
    "PluginConfigValidationError",
    "ValueType",
    "effective_values",
    "load",
    "parse_schema",
    "reset",
    "schema_to_jsonable",
    "update",
]
