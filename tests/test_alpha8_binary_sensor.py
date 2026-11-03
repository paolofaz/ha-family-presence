"""Alpha 8: shadow aggregate entity is ON iff all FSM members are AWAY."""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State

BINARY_SENSOR_FILE = (
    Path(__file__).resolve().parents[1] / "custom_components"
    / "family_presence" / "binary_sensor.py"
)


def load_binary_sensor_module():
    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    binary = types.ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorEntity:
        pass

    binary.BinarySensorEntity = BinarySensorEntity
    components.binary_sensor = binary
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
        "homeassistant.components.binary_sensor": binary,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.entity_platform": platform,
    }
    name = "custom_components.family_presence.binary_sensor"
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(name, BINARY_SENSOR_FILE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


class ShadowAllAwayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
        self.raw = {
            "phone": "home", "watch": "on",
            "reference": "home", "phone2": "not_home",
            "reference2": "home",
        }
        self.members = [
            PersonSources("paolo", "Paolo", iphone="phone", watch="watch",
                          reference="reference"),
            PersonSources("giulia", "Giulia", iphone="phone2",
                          reference="reference2"),
        ]
        self.engine = self.new()
        self.module = load_binary_sensor_module()

    def new(self):
        return ShadowCoordinator(
            self.members, read_state=self.raw.get,
            clock=lambda: self.now,
        )

    async def entity(self, engine=None):
        engine = engine or self.engine
        entry = types.SimpleNamespace(
            entry_id="test-entry",
            runtime_data=types.SimpleNamespace(engine=engine),
        )
        registered = []
        await self.module.async_setup_entry(None, entry, registered.extend)
        self.assertEqual(len(registered), 1)
        return registered[0]

    async def test_entity_is_diagnostic_not_the_legacy_binary_sensor(self):
        sensor = await self.entity()
        self.assertEqual(sensor._attr_entity_category, "diagnostic")
        self.assertIn("Shadow", sensor._attr_name)
        attrs = sensor.extra_state_attributes
        self.assertTrue(attrs["not_the_legacy_casa_certamente_vuota"])
        self.assertTrue(attrs["do_not_use_for_automations"])
        self.assertEqual(attrs["aggregation_rule"], "all_configured_members_away")
        self.assertFalse(sensor.is_on)

    async def test_two_manual_away_events_turn_on_only_after_last_member(self):
        sensor = await self.entity()
        await self.engine.force_state("paolo", State.AWAY)
        self.assertFalse(sensor.is_on)
        await self.engine.force_state("giulia", State.AWAY)
        self.assertTrue(sensor.is_on)
        self.assertEqual(sensor.extra_state_attributes["non_away_members"], [])
        self.assertEqual(sensor.extra_state_attributes["member_reasons"]["Paolo"],
                         "away_forzato")
        self.assertEqual(sensor.extra_state_attributes["member_reasons"]["Giulia"],
                         "away_forzato")

    async def test_force_home_turns_off_then_force_away_reactivates(self):
        sensor = await self.entity()
        for key in self.engine.people:
            await self.engine.force_state(key, State.AWAY)
        self.assertTrue(sensor.is_on)
        await self.engine.force_state("giulia", State.HOME)
        self.assertFalse(sensor.is_on)
        self.assertEqual(sensor.extra_state_attributes["non_away_members"], ["Giulia"])
        await self.engine.force_state("giulia", State.AWAY)
        self.assertTrue(sensor.is_on)

    async def test_restored_all_away_stays_on_after_restart(self):
        for key in self.engine.people:
            await self.engine.force_state(key, State.AWAY)
        restarted = self.new()
        self.assertEqual(restarted.restore_snapshot(self.engine.snapshot()), 2)
        sensor = await self.entity(restarted)
        self.assertTrue(sensor.is_on)
        self.assertTrue(restarted.runtime["paolo"].restored_from_storage)

    async def test_conflicting_raw_sensors_are_warnings_not_vetoes(self):
        sensor = await self.entity()
        for key in self.engine.people:
            await self.engine.force_state(key, State.AWAY)
        self.assertTrue(sensor.is_on)
        attrs = sensor.extra_state_attributes
        self.assertIn("iphone_home_con_fsm_away", attrs["source_warnings"]["Paolo"])
        self.assertIn("watch_on_con_fsm_away", attrs["source_warnings"]["Paolo"])

    async def test_valid_later_iphone_event_changes_aggregate(self):
        sensor = await self.entity()
        for key in self.engine.people:
            await self.engine.force_state(key, State.AWAY)
        self.assertTrue(sensor.is_on)
        self.now += timedelta(seconds=2)
        await self.engine.process("paolo", Event.IPHONE_ARRIVED,
                                  event_time=self.now)
        self.assertFalse(sensor.is_on)

    async def test_comparison_attributes_follow_legacy_helper_events(self):
        sensor = await self.entity()
        for key in self.engine.people:
            await self.engine.force_state(key, State.HOME)
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["legacy_comparison_status"], "aligned")
        self.assertIs(attrs["legacy_expected_all_away"], False)
        self.assertIs(attrs["aggregate_matches_legacy"], True)
        self.assertEqual(attrs["legacy_differing_members"], [])

        self.now += timedelta(seconds=1)
        await self.engine.force_state("paolo", State.AWAY)
        self.now += timedelta(seconds=1)
        await self.engine.force_state("giulia", State.AWAY)
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["legacy_comparison_status"], "aggregate_divergence")
        self.assertIs(attrs["legacy_expected_all_away"], False)
        self.assertIs(attrs["aggregate_matches_legacy"], False)
        self.assertEqual(attrs["legacy_differing_members"], ["Paolo", "Giulia"])
        self.assertIsNotNone(attrs["legacy_divergence_since"])

        self.raw["reference"] = "away"
        self.engine.notify_source_update("paolo")
        self.raw["reference2"] = "away"
        self.engine.notify_source_update("giulia")
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["legacy_comparison_status"], "aligned")
        self.assertIs(attrs["legacy_expected_all_away"], True)
        self.assertIs(attrs["aggregate_matches_legacy"], True)
        self.assertIsNone(attrs["legacy_divergence_since"])

    async def test_unavailable_reference_does_not_forge_comparison(self):
        sensor = await self.entity()
        self.raw["reference2"] = "unavailable"
        self.engine.notify_source_update("giulia")
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["legacy_comparison_status"], "reference_unavailable")
        self.assertEqual(attrs["legacy_unavailable_reference_members"], ["Giulia"])
        self.assertIsNone(attrs["legacy_expected_all_away"])
        self.assertIsNone(attrs["aggregate_matches_legacy"])

    async def test_live_legacy_binary_attributes_independent_of_expected(self):
        self.raw["legacy_actual"] = "off"
        engine = ShadowCoordinator(
            self.members,
            read_state=self.raw.get,
            clock=lambda: self.now,
            legacy_aggregate="legacy_actual",
        )
        sensor = await self.entity(engine)
        for key in engine.people:
            await engine.force_state(key, State.AWAY)
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["actual_legacy_state"], "off")
        self.assertIs(attrs["actual_legacy_all_away"], False)
        self.assertIs(attrs["actual_legacy_matches_shadow"], False)
        self.assertIs(attrs["legacy_expected_all_away"], False)
        self.assertIs(attrs["actual_legacy_matches_expected"], True)

        self.raw["legacy_actual"] = "on"
        engine.notify_legacy_aggregate_update()
        attrs = sensor.extra_state_attributes
        self.assertIs(attrs["actual_legacy_matches_shadow"], True)
        self.assertIs(attrs["actual_legacy_matches_expected"], False)
        self.assertTrue(sensor.is_on)

    async def test_near_home_and_unknown_are_off(self):
        sensor = await self.entity()
        for key in self.engine.people:
            await self.engine.force_state(key, State.AWAY)
        self.assertTrue(sensor.is_on)
        self.engine.runtime["giulia"].state = State.NEAR_HOME
        self.assertFalse(sensor.is_on)
        self.engine.runtime["giulia"].state = None
        self.assertFalse(sensor.is_on)
        self.engine.runtime["giulia"].state = State.AWAY
        self.assertTrue(sensor.is_on)


if __name__ == "__main__":
    unittest.main()
