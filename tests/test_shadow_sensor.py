"""Diagnostic shadow sensor shows provenance after a restart (without HA runtime)."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State

SENSOR_FILE = (
    Path(__file__).resolve().parents[1] / "custom_components"
    / "family_presence" / "sensor.py"
)


def load_sensor_class():
    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    sensors = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        pass

    sensors.SensorEntity = SensorEntity
    components.sensor = sensors
    const = types.ModuleType("homeassistant.const")
    const.EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda cb: cb
    helpers = types.ModuleType("homeassistant.helpers")
    platform = types.ModuleType("homeassistant.helpers.entity_platform")
    platform.AddConfigEntryEntitiesCallback = object
    modules = {
        "homeassistant": ha,
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensors,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.entity_platform": platform,
    }
    name = "custom_components.family_presence.sensor"
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(name, SENSOR_FILE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module.ShadowPersonSensor


class ShadowSensorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 7, 0, tzinfo=timezone.utc)
        self.s = {"phone": "home", "legacy": "home"}

        async def sleep(_):
            return None

        self.new = lambda: ShadowCoordinator(
            [PersonSources("person", "Member", iphone="phone", reference="legacy")],
            read_state=self.s.get,
            clock=lambda: self.now,
            sleep=sleep,
        )
        self.cls = load_sensor_class()

    async def test_diagnostic_reason_and_provenance_survive_restart(self):
        before = self.new()
        await before.process("person", Event.IPHONE_LEFT, event_time=self.now)
        saved = before.snapshot()
        self.s["legacy"] = "away"
        after = self.new()
        after.restore_snapshot(saved)
        sensor = self.cls("entry", after, "person")
        self.assertEqual(sensor.native_value, "away")
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["reason"], "iPhone left home zone")
        self.assertEqual(attrs["state_origin"], "legacy_reference")
        self.assertEqual(attrs["reason_origin"], "saved_snapshot_matched_legacy")
        self.assertFalse(attrs["restored_from_storage"])
        self.assertTrue(attrs["matches_legacy"])
        self.assertEqual(attrs["mode"], "shadow_only")

    async def test_diagnostic_reports_missing_reason_instead_of_inventing_it(self):
        coordinator = self.new()
        sensor = self.cls("entry", coordinator, "person")
        attrs = sensor.extra_state_attributes
        self.assertIsNone(attrs["reason"])
        self.assertEqual(attrs["reason_origin"], "not_recorded")
        self.assertEqual(attrs["state_origin"], "legacy_reference")


if __name__ == "__main__":
    unittest.main()
