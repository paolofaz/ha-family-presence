"""RC5 regression tests for HA virtual device grouping and legacy-free outputs."""
from __future__ import annotations
from datetime import datetime, timezone
import types
import unittest

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.presentation import FINAL
from test_shadow_sensor import load_sensor_module
from test_alpha8_binary_sensor import load_binary_sensor_module
from test_manual_buttons import load_buttons, FakeStore
from test_source_adapter import load_source_module, FakeHA, ha_event
from custom_components.family_presence.fsm import State


class RC5EntityGroupingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = ShadowCoordinator(
            [PersonSources("paolo", "Paolo", iphone="device_tracker.paolo")],
            read_state=lambda _id: None,
        )

    async def test_all_entities_share_one_household_device(self):
        sensor = load_sensor_module()
        binary = load_binary_sensor_module()
        buttons = load_buttons()
        presence = sensor.ShadowPersonSensor("entry", self.engine, "paolo", FINAL)
        household = sensor.ShadowHouseholdSensor("entry", self.engine, FINAL)
        all_away = binary.ShadowAllAwayBinarySensor("entry", self.engine, FINAL)
        runtime = types.SimpleNamespace(
            engine=self.engine, store=FakeStore(), profile=FINAL
        )
        home_button = buttons.ShadowForceButton(
            "entry", runtime, "paolo", State.HOME
        )
        away_button = buttons.ShadowForceButton(
            "entry", runtime, "paolo", State.AWAY
        )
        self.assertEqual(presence._attr_name, "Presenza Paolo")
        self.assertTrue(presence._attr_has_entity_name)
        self.assertEqual(presence._attr_unique_id, "entry_paolo_shadow")
        self.assertEqual(
            presence._attr_device_info["identifiers"],
            home_button._attr_device_info["identifiers"],
        )
        self.assertEqual(
            presence._attr_device_info["identifiers"],
            away_button._attr_device_info["identifiers"],
        )
        self.assertEqual(
            household._attr_device_info["identifiers"],
            all_away._attr_device_info["identifiers"],
        )
        self.assertEqual(
            household._attr_device_info["identifiers"],
            presence._attr_device_info["identifiers"],
        )
        self.assertEqual(presence._attr_device_info["name"], "Casa")
        self.assertEqual(all_away._attr_name, "Casa certamente vuota")
        self.assertEqual(home_button._attr_name, "Paolo — Forza a casa")

    async def test_final_state_attributes_do_not_expose_yaml_comparison(self):
        sensor = load_sensor_module()
        binary = load_binary_sensor_module()
        presence = sensor.ShadowPersonSensor("entry", self.engine, "paolo", FINAL)
        household = sensor.ShadowHouseholdSensor("entry", self.engine, FINAL)
        all_away = binary.ShadowAllAwayBinarySensor("entry", self.engine, FINAL)
        self.assertNotIn("legacy_state", presence.extra_state_attributes)
        self.assertNotIn("matches_legacy", presence.extra_state_attributes)
        self.assertNotIn("legacy_comparison_status", household.extra_state_attributes)
        self.assertNotIn("legacy_comparison_status", all_away.extra_state_attributes)
        self.assertFalse(all_away.is_on)
        await self.engine.force_state("paolo", State.AWAY)
        self.assertTrue(all_away.is_on)

    async def test_retained_old_config_does_not_read_old_yaml_helpers(self):
        sources, _ = load_source_module()
        people = sources._person_specs({"people": [{
            "person_id": "paolo", "person_name": "Paolo",
            "iphone_tracker": "device_tracker.paolo",
            "legacy_presence_entity": "input_select.presenza_paolo",
        }]})
        self.assertIsNone(people[0].reference)


class RC5GateLockRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_lock_unlock_records_gate_evidence(self):
        sources, _ = load_source_module()
        now = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
        engine = ShadowCoordinator(
            [PersonSources("paolo", "Paolo", iphone="device_tracker.paolo")],
            read_state=lambda _id: None,
        )
        adapter = sources.ShadowSourceAdapter(
            FakeHA(), {"gate_entities": ["lock.cancello"]}, engine
        )
        adapter.start()
        try:
            adapter._changed(ha_event("lock.cancello", "locked", "unlocked", now))
            self.assertEqual(engine._physical.get("gate"), now)
            # Locking the gate is NOT an arrival/departure event.
            adapter._changed(ha_event("lock.cancello", "unlocked", "locked", now))
            self.assertEqual(engine._physical.get("gate"), now)
        finally:
            await adapter.async_stop()


if __name__ == "__main__":
    unittest.main()
