"""Diagnostic shadow sensor shows provenance after a restart (without HA runtime)."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
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


def load_sensor_module():
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
    return module


def load_sensor_class():
    return load_sensor_module().ShadowPersonSensor


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
        self.assertEqual(attrs["reason"], "iPhone uscito dalla zona casa")
        self.assertEqual(attrs["state_origin"], "saved_shadow_unverified")
        self.assertEqual(attrs["reason_origin"], "saved_snapshot_unverified")
        self.assertTrue(attrs["restored_from_storage"])
        self.assertTrue(attrs["matches_legacy"])
        self.assertEqual(attrs["mode"], "shadow_only")

    async def test_yaml_can_disagree_without_rewriting_shadow(self):
        before = self.new()
        await before.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.s["legacy"] = "home"
        after = self.new()
        after.restore_snapshot(before.snapshot())
        sensor = self.cls("entry", after, "person")
        self.assertEqual(sensor.native_value, "away")
        self.assertEqual(sensor.extra_state_attributes["legacy_state"], "home")
        self.assertIs(sensor.extra_state_attributes["matches_legacy"], False)
        self.assertEqual(sensor.extra_state_attributes["reason"],
                         "iPhone uscito dalla zona casa")
        self.s["legacy"] = "away"
        self.assertEqual(sensor.native_value, "away")
        self.assertIs(sensor.extra_state_attributes["matches_legacy"], True)

    async def test_bag_schedule_is_visible_to_lovelace(self):
        engine = ShadowCoordinator(
            [PersonSources("kid", "Member", bag="bag")],
            read_state=self.s.get, clock=lambda: self.now,
        )
        attrs = self.cls("entry", engine, "kid").extra_state_attributes
        self.assertEqual(attrs["bag_window_start"], "07:00")
        self.assertEqual(attrs["bag_window_end"], "09:10")
        self.assertTrue(attrs["bag_enabled"])
        self.assertEqual(attrs["bag_days"], [0, 1, 2, 3, 4])

    async def test_manual_force_is_visible_to_lovelace(self):
        engine = ShadowCoordinator(
            [PersonSources("kid", "Member")],
            read_state=self.s.get, clock=lambda: self.now,
        )
        await engine.force_state("kid", State.HOME)
        attrs = self.cls("entry", engine, "kid").extra_state_attributes
        self.assertEqual(attrs["manual_last_action"], "manual_home")
        self.assertIsNotNone(attrs["manual_last_action_at"])
        self.assertEqual(attrs["reason"], "Forzato in casa manualmente")
        self.assertEqual(attrs["state_origin"], "manual_force")

    async def test_divergence_fields_and_ignored_event_are_exposed(self):
        engine = self.new()
        await engine.process("person", Event.IPHONE_LEFT, event_time=self.now)
        sensor = self.cls("entry", engine, "person")
        self.assertEqual(sensor.extra_state_attributes["comparison_status"], "diverged")
        self.assertIsNotNone(sensor.extra_state_attributes["divergence_since"])
        await engine.process("person", Event.WATCH_LOST, event_time=self.now)
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["last_ignored_event"], "watch_off")
        self.assertIn("mancano condizioni", attrs["last_ignored_reason"])
        self.assertEqual(attrs["ignored_event_count"], 1)
        self.s["legacy"] = "away"
        engine.notify_source_update("person")
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["comparison_status"], "aligned")
        self.assertIsNone(attrs["divergence_since"])

    async def test_household_sensor_is_diagnostic_only_and_reports_blockers(self):
        module = load_sensor_module()
        engine = self.new()
        entry = types.SimpleNamespace(
            entry_id="entry", runtime_data=types.SimpleNamespace(engine=engine)
        )
        registered = []
        await module.async_setup_entry(None, entry, registered.extend)
        self.assertEqual(len(registered), 2)
        household = next(x for x in registered
                         if isinstance(x, module.ShadowHouseholdSensor))
        self.assertEqual(household.native_value, "indeterminate")
        attrs = household.extra_state_attributes
        self.assertEqual(attrs["mode"], "shadow_only")
        self.assertTrue(attrs["do_not_use_for_automations"])
        self.assertTrue(attrs["candidate_empty_is_not_alarm_permission"])
        self.assertIn("Member", attrs["unresolved_members"])
        self.assertIsNone(attrs["all_away_internal"])

        await engine.force_state("person", State.AWAY)
        attrs = household.extra_state_attributes
        self.assertEqual(household.native_value, "indeterminate")
        self.assertEqual(attrs["member_diagnostics"]["Member"]["reason"],
                         "away_manuale_non_verificato")
        self.assertIsNone(attrs["all_away_internal"])

        self.s["phone"] = "not_home"
        self.now += timedelta(seconds=2)  # New sensor event must follow manual force.
        await engine.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(household.native_value, "candidate_empty")
        self.assertIs(household.extra_state_attributes["all_away_internal"], True)

    async def test_diagnostic_reports_missing_reason_instead_of_inventing_it(self):
        coordinator = self.new()
        sensor = self.cls("entry", coordinator, "person")
        attrs = sensor.extra_state_attributes
        self.assertIsNone(attrs["reason"])
        self.assertEqual(attrs["reason_origin"], "not_recorded")
        self.assertEqual(attrs["state_origin"], "unknown")


if __name__ == "__main__":
    unittest.main()
