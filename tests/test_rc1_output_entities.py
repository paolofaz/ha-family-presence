"""RC1 proof that the same registered output can switch labels without state drift."""
import types
import unittest

from test_alpha8_binary_sensor import load_binary_sensor_module
from test_manual_buttons import FakeStore, load_buttons
from test_shadow_sensor import load_sensor_module

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import State
from custom_components.family_presence.presentation import FINAL, SHADOW


class RC1OutputEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = ShadowCoordinator(
            [PersonSources("paolo", "Paolo", iphone="device_tracker.phone")],
            read_state=lambda _id: None,
        )

    async def test_binary_profile_changes_metadata_but_never_truth_table(self):
        binary = load_binary_sensor_module()
        shadow = binary.ShadowAllAwayBinarySensor("entry", self.engine, SHADOW)
        final = binary.ShadowAllAwayBinarySensor("entry", self.engine, FINAL)
        self.assertEqual(shadow._attr_unique_id, final._attr_unique_id)
        self.assertIsNone(final._attr_entity_category)
        self.assertEqual(shadow._attr_entity_category, "diagnostic")
        self.assertEqual(final._attr_name, "Casa certamente vuota")
        self.assertFalse(final.is_on)
        self.assertFalse(final.extra_state_attributes["do_not_use_for_automations"])
        self.assertTrue(final.extra_state_attributes["cutover_active"])
        await self.engine.force_state("paolo", State.AWAY)
        self.assertTrue(shadow.is_on)
        self.assertTrue(final.is_on)
        await self.engine.force_state("paolo", State.HOME)
        self.assertFalse(shadow.is_on)
        self.assertFalse(final.is_on)

    async def test_person_final_keeps_registered_identity_and_raw_state(self):
        sensor = load_sensor_module()
        shadow = sensor.ShadowPersonSensor("entry", self.engine, "paolo", SHADOW)
        final = sensor.ShadowPersonSensor("entry", self.engine, "paolo", FINAL)
        self.assertEqual(shadow._attr_unique_id, final._attr_unique_id)
        self.assertIsNone(final._attr_entity_category)
        self.assertEqual(final._attr_name, "Presenza")
        self.assertIsNone(final.native_value)
        await self.engine.force_state("paolo", State.AWAY)
        self.assertEqual(final.native_value, "away")
        self.assertEqual(final.extra_state_attributes["mode"], "final")
        self.assertTrue(final.extra_state_attributes["cutover_active"])

    async def test_manual_buttons_keep_id_and_only_write_fsm_snapshot(self):
        buttons = load_buttons()
        store = FakeStore()
        shadow = buttons.ShadowForceButton(
            "entry", types.SimpleNamespace(engine=self.engine, store=store,
                                           profile=SHADOW), "paolo", State.AWAY
        )
        final = buttons.ShadowForceButton(
            "entry", types.SimpleNamespace(engine=self.engine, store=store,
                                           profile=FINAL), "paolo", State.AWAY
        )
        self.assertEqual(shadow._attr_unique_id, final._attr_unique_id)
        self.assertEqual(shadow._attr_entity_category, "diagnostic")
        self.assertIsNone(final._attr_entity_category)
        await final.async_press()
        self.assertEqual(self.engine.state("paolo"), State.AWAY)
        self.assertEqual(len(store.saved), 1)
        self.assertEqual(store.saved[0]["people"]["paolo"]["state"], "away")


if __name__ == "__main__":
    unittest.main()
