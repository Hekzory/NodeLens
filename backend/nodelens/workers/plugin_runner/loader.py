"""Plugin discovery and dynamic loading utilities."""

from __future__ import annotations

import importlib.util
import sys
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from nodelens.sdk.base_plugin import BasePlugin

if TYPE_CHECKING:
    from pathlib import Path


def load_manifest(plugin_dir: Path) -> dict[str, Any]:
    """Read and validate the ``manifest.yaml`` inside *plugin_dir*."""
    from nodelens.plugin_config.registry import parse_schema, schema_to_jsonable

    yaml = YAML()
    manifest_path = plugin_dir / "manifest.yaml"
    with manifest_path.open() as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"Manifest must be a YAML mapping, got {type(data).__name__}")

    # Optional: validate and normalise the config_schema block. We round-trip
    # through parse_schema so a bad entry surfaces here (the supervisor turns
    # this into a "skip plugin, log warning") and replace the raw value with
    # the canonical JSON-able form so downstream consumers don't have to
    # re-coerce.
    if data.get("config_schema") is not None:
        try:
            fields = parse_schema(data["config_schema"])
        except ValueError as exc:
            raise TypeError(f"config_schema invalid: {exc}") from None
        data["config_schema"] = schema_to_jsonable(fields)

    return data


def load_plugin_class(plugin_dir: Path, entry_point: str) -> type[BasePlugin]:
    """Import and return the plugin class specified by *entry_point*.

    *entry_point* format: ``"module_file:ClassName"``
    e.g. ``"plugin:DemoSenderPlugin"`` → loads ``plugin.py`` and returns
    the ``DemoSenderPlugin`` class.
    """
    module_file, class_name = entry_point.split(":")
    module_path = plugin_dir / f"{module_file}.py"

    if not module_path.exists():
        raise FileNotFoundError(f"Plugin module not found: {module_path}")

    fq_name = f"nodelens_plugin_{plugin_dir.parent.name}_{plugin_dir.name}_{module_file}"

    spec = importlib.util.spec_from_file_location(fq_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[fq_name] = module
    spec.loader.exec_module(module)

    cls = getattr(module, class_name, None)
    if cls is None:
        raise ImportError(f"Class {class_name!r} not found in {module_path}")
    if not (isinstance(cls, type) and issubclass(cls, BasePlugin)):
        raise TypeError(f"{class_name!r} is not a subclass of BasePlugin")

    return cls
