"""Plugin discovery and dynamic loading utilities."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nodelens.sdk.base_plugin import BasePlugin


def load_manifest(plugin_dir: Path) -> dict[str, Any]:
    """Read and validate the ``manifest.yaml`` inside *plugin_dir*."""
    yaml = YAML()
    manifest_path = plugin_dir / "manifest.yaml"
    with manifest_path.open() as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"Manifest must be a YAML mapping, got {type(data).__name__}")
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
