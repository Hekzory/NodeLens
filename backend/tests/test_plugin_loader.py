"""Tests for plugin manifest loading and dynamic class loading."""

import textwrap
from pathlib import Path

import pytest

from nodelens.sdk.base_plugin import BasePlugin
from nodelens.workers.plugin_runner.loader import load_manifest, load_plugin_class

# ── Helpers ──────────────────────────────────────────────────────

_VALID_MANIFEST = textwrap.dedent("""\
    id: "10000000-0000-0000-0000-000000000001"
    name: test_plugin
    display_name: "Test Plugin"
    version: "0.1.0"
    type: device
    entry_point: "plugin:TestPlugin"
""")

_VALID_PLUGIN_CODE = textwrap.dedent("""\
    from nodelens.sdk import BasePlugin

    class TestPlugin(BasePlugin):
        name = "test_plugin"
        version = "0.1.0"

        async def configure(self, settings):
            pass

        async def start(self):
            pass

        async def stop(self):
            pass
""")

_NOT_BASE_PLUGIN_CODE = textwrap.dedent("""\
    class NotAPlugin:
        pass
""")


def _make_plugin_dir(tmp_path: Path, manifest: str = _VALID_MANIFEST, plugin_code: str = _VALID_PLUGIN_CODE) -> Path:
    plugin_dir = tmp_path / "devices" / "test_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.yaml").write_text(manifest)
    (plugin_dir / "plugin.py").write_text(plugin_code)
    return plugin_dir


# ── Manifest loading ─────────────────────────────────────────────

class TestLoadManifest:
    def test_valid_manifest_returns_dict(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        manifest = load_manifest(plugin_dir)
        assert isinstance(manifest, dict)
        assert manifest["name"] == "test_plugin"
        assert manifest["version"] == "0.1.0"

    def test_missing_manifest_file_raises_error(self, tmp_path):
        plugin_dir = tmp_path / "devices" / "no_manifest"
        plugin_dir.mkdir(parents=True)
        with pytest.raises((FileNotFoundError, OSError)):
            load_manifest(plugin_dir)

    def test_non_mapping_yaml_raises_typeerror(self, tmp_path):
        plugin_dir = tmp_path / "devices" / "bad_manifest"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text("- item1\n- item2\n")
        with pytest.raises(TypeError, match="mapping"):
            load_manifest(plugin_dir)


# ── Plugin class loading ─────────────────────────────────────────

class TestLoadPluginClass:
    def test_valid_entry_point_returns_base_plugin_subclass(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        cls = load_plugin_class(plugin_dir, "plugin:TestPlugin")
        assert cls is not None
        assert issubclass(cls, BasePlugin)

    def test_missing_module_file_raises_filenotfounderror(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_plugin_class(plugin_dir, "nonexistent_module:TestPlugin")

    def test_missing_class_in_module_raises_importerror(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        with pytest.raises(ImportError):
            load_plugin_class(plugin_dir, "plugin:NoSuchClass")

    def test_class_not_base_plugin_subclass_raises_typeerror(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path, plugin_code=_NOT_BASE_PLUGIN_CODE)
        with pytest.raises(TypeError):
            load_plugin_class(plugin_dir, "plugin:NotAPlugin")

    def test_malformed_entry_point_no_colon_raises_valueerror(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        with pytest.raises(ValueError, match="not enough values to unpack"):
            load_plugin_class(plugin_dir, "plugin_without_colon")


# ── config_schema parsing inside the manifest loader ─────────────

_MANIFEST_WITH_CONFIG_SCHEMA = textwrap.dedent("""\
    id: "10000000-0000-0000-0000-000000000001"
    name: test_plugin
    display_name: "Test Plugin"
    version: "0.1.0"
    type: device
    entry_point: "plugin:TestPlugin"
    config_schema:
      - key: smtp_host
        label: "SMTP host"
        group: connection
        value_type: string
        default: "localhost"
      - key: smtp_port
        label: "SMTP port"
        group: connection
        value_type: int
        default: 25
        min: 1
        max: 65535
      - key: smtp_password
        label: "Password"
        group: connection
        value_type: secret
        default: ""
""")


class TestConfigSchemaParsing:
    def test_valid_block_normalised_to_jsonable_form(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path, manifest=_MANIFEST_WITH_CONFIG_SCHEMA)
        manifest = load_manifest(plugin_dir)
        schema = manifest["config_schema"]
        assert isinstance(schema, list)
        assert len(schema) == 3
        # Every entry is a plain dict with expected keys (round-tripped through
        # parse_schema → schema_to_jsonable).
        first = schema[0]
        assert first == {
            "key": "smtp_host",
            "label": "SMTP host",
            "group": "connection",
            "value_type": "string",
            "default": "localhost",
            "help": "",
            "unit": None,
            "min": None,
            "max": None,
            "requires_restart": False,
        }
        secret = schema[2]
        assert secret["value_type"] == "secret"
        assert secret["default"] == ""

    def test_missing_required_field_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            id: "10000000-0000-0000-0000-000000000001"
            name: test_plugin
            display_name: "Test Plugin"
            version: "0.1.0"
            type: device
            entry_point: "plugin:TestPlugin"
            config_schema:
              - label: "Missing key"
                value_type: string
        """)
        plugin_dir = tmp_path / "devices" / "bad"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text(bad)
        (plugin_dir / "plugin.py").write_text(_VALID_PLUGIN_CODE)
        with pytest.raises(TypeError, match="config_schema invalid"):
            load_manifest(plugin_dir)

    def test_unknown_value_type_raises(self, tmp_path):
        bad = _MANIFEST_WITH_CONFIG_SCHEMA.replace("value_type: string", "value_type: bogus")
        plugin_dir = tmp_path / "devices" / "bad"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text(bad)
        (plugin_dir / "plugin.py").write_text(_VALID_PLUGIN_CODE)
        with pytest.raises(TypeError, match="unknown value_type"):
            load_manifest(plugin_dir)

    def test_duplicate_key_raises(self, tmp_path):
        dup = textwrap.dedent("""\
            id: "10000000-0000-0000-0000-000000000001"
            name: test_plugin
            display_name: "Test Plugin"
            version: "0.1.0"
            type: device
            entry_point: "plugin:TestPlugin"
            config_schema:
              - key: foo
                label: "Foo"
                value_type: string
              - key: foo
                label: "Foo Again"
                value_type: int
        """)
        plugin_dir = tmp_path / "devices" / "dup"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text(dup)
        (plugin_dir / "plugin.py").write_text(_VALID_PLUGIN_CODE)
        with pytest.raises(TypeError, match="duplicate key"):
            load_manifest(plugin_dir)

    def test_invalid_default_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            id: "10000000-0000-0000-0000-000000000001"
            name: test_plugin
            display_name: "Test Plugin"
            version: "0.1.0"
            type: device
            entry_point: "plugin:TestPlugin"
            config_schema:
              - key: port
                label: "Port"
                value_type: int
                default: 0
                min: 1
                max: 65535
        """)
        plugin_dir = tmp_path / "devices" / "bad_default"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text(bad)
        (plugin_dir / "plugin.py").write_text(_VALID_PLUGIN_CODE)
        with pytest.raises(TypeError, match="invalid default"):
            load_manifest(plugin_dir)

    def test_no_config_schema_block_is_fine(self, tmp_path):
        plugin_dir = _make_plugin_dir(tmp_path)
        manifest = load_manifest(plugin_dir)
        assert "config_schema" not in manifest
