"""Tests for plugin supervisor's discover_plugins() function."""

import textwrap
from pathlib import Path

from nodelens.workers.plugin_runner.__main__ import discover_plugins

_FULL_MANIFEST = textwrap.dedent("""\
    id: "10000000-0000-0000-0000-000000000001"
    name: test_plugin
    display_name: "Test Plugin"
    version: "0.1.0"
    type: device
    entry_point: "plugin:TestPlugin"
""")

_FULL_MANIFEST_B = textwrap.dedent("""\
    id: "10000000-0000-0000-0000-000000000002"
    name: test_plugin_b
    display_name: "Test Plugin B"
    version: "0.1.0"
    type: device
    entry_point: "plugin:TestPlugin"
""")

_INCOMPLETE_MANIFEST = textwrap.dedent("""\
    name: incomplete_plugin
    display_name: "Missing Fields"
""")


def _make_plugin(base_dir: Path, type_name: str, plugin_name: str, manifest: str) -> Path:
    plugin_dir = base_dir / type_name / plugin_name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.yaml").write_text(manifest)
    return plugin_dir


class TestDiscoverPlugins:
    def test_valid_plugin_is_discovered(self, tmp_path):
        _make_plugin(tmp_path, "devices", "my_plugin", _FULL_MANIFEST)
        found = discover_plugins(tmp_path)
        assert len(found) == 1
        dirs = list(found.values())
        assert dirs[0].name == "my_plugin"

    def test_multiple_plugins_are_all_discovered(self, tmp_path):
        _make_plugin(tmp_path, "devices", "plugin_a", _FULL_MANIFEST)
        _make_plugin(tmp_path, "devices", "plugin_b", _FULL_MANIFEST_B)
        found = discover_plugins(tmp_path)
        names = {p.name for p in found.values()}
        assert names == {"plugin_a", "plugin_b"}

    def test_dir_without_manifest_is_skipped(self, tmp_path):
        # Create a dir with no manifest.yaml
        no_manifest_dir = tmp_path / "devices" / "bare_dir"
        no_manifest_dir.mkdir(parents=True)
        found = discover_plugins(tmp_path)
        assert found == {}

    def test_plugin_with_incomplete_manifest_is_skipped(self, tmp_path):
        _make_plugin(tmp_path, "devices", "bad_plugin", _INCOMPLETE_MANIFEST)
        found = discover_plugins(tmp_path)
        assert found == {}

    def test_nonexistent_base_dir_returns_empty_list(self, tmp_path):
        missing_dir = tmp_path / "does_not_exist"
        found = discover_plugins(missing_dir)
        assert found == {}

    def test_valid_plugin_mixed_with_invalid_only_valid_returned(self, tmp_path):
        _make_plugin(tmp_path, "devices", "good_plugin", _FULL_MANIFEST)
        _make_plugin(tmp_path, "devices", "bad_plugin", _INCOMPLETE_MANIFEST)
        found = discover_plugins(tmp_path)
        assert len(found) == 1
        dirs = list(found.values())
        assert dirs[0].name == "good_plugin"
