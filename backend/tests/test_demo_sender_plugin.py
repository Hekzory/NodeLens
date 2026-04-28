"""Unit tests for the demo_sender device plugin's config-driven sensor list."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PLUGIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "devices"
    / "demo_sender"
    / "plugin.py"
)


def _load_plugin_module():
    spec = importlib.util.spec_from_file_location("nodelens_test_demo_sender", _PLUGIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nodelens_test_demo_sender"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin_mod():
    yield _load_plugin_module()
    sys.modules.pop("nodelens_test_demo_sender", None)


@pytest.fixture
def plugin(plugin_mod):
    return plugin_mod.DemoSenderPlugin()


class TestRuntimeSensors:
    async def test_defaults_when_no_config(self, plugin, plugin_mod):
        await plugin.configure({})
        sensors = plugin._runtime_sensors()
        assert len(sensors) == 5
        # First spec: living_room_temp — DEVICE_1 / SENSOR_TEMP_1, 18-28 @ 3s.
        device_id, sensor_id, lo, hi, interval = sensors[0]
        assert device_id == plugin_mod.DEVICE_1
        assert sensor_id == plugin_mod.SENSOR_TEMP_1
        assert lo == 18.0
        assert hi == 28.0
        assert interval == 3.0
        # Last spec: door_battery — slow cadence by default.
        assert sensors[-1][4] == 15.0

    async def test_overrides_replace_per_sensor_values(self, plugin):
        await plugin.configure({
            "living_room_temp_min": 5.0,
            "living_room_temp_max": 10.0,
            "living_room_temp_interval_s": 0.5,
            "door_battery_interval_s": 2.0,
        })
        sensors = plugin._runtime_sensors()
        # Living room temp values + interval all overridden.
        assert sensors[0][2] == 5.0
        assert sensors[0][3] == 10.0
        assert sensors[0][4] == 0.5
        # Other sensors keep their defaults.
        assert sensors[1][2] == 30.0  # humidity min default
        # Door battery interval was overridden.
        assert sensors[-1][4] == 2.0
        # Door battery values still defaults.
        assert sensors[-1][2] == 3.0
        assert sensors[-1][3] == 4.2

    async def test_int_value_for_float_field_coerced(self, plugin):
        # The runtime accepts ints in the JSONB blob — ``float()`` keeps the
        # plugin from blowing up on round-tripped numbers that landed as int.
        await plugin.configure({"living_room_temp_min": 5})
        sensors = plugin._runtime_sensors()
        assert sensors[0][2] == 5.0
        assert isinstance(sensors[0][2], float)


class TestManifestSchemaRoundTrip:
    """Catches silent drift between manifest defaults and code defaults."""

    def test_manifest_defaults_match_sensor_specs(self, plugin_mod):
        from ruamel.yaml import YAML

        manifest_path = _PLUGIN_PATH.parent / "manifest.yaml"
        manifest = YAML().load(manifest_path.read_text())
        schema = {entry["key"]: entry for entry in manifest["config_schema"]}

        for prefix, _did, _sid, def_lo, def_hi, def_interval in plugin_mod.SENSOR_SPECS:
            assert schema[f"{prefix}_min"]["default"] == def_lo, prefix
            assert schema[f"{prefix}_max"]["default"] == def_hi, prefix
            assert schema[f"{prefix}_interval_s"]["default"] == def_interval, prefix

        assert schema["tick_interval_s"]["default"] == plugin_mod.DEFAULT_TICK_INTERVAL_S
        assert (
            schema["registration_settle_s"]["default"]
            == plugin_mod.DEFAULT_REGISTRATION_SETTLE_S
        )
