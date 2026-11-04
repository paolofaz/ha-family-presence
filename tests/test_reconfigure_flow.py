"""Contract tests for Home Assistant's reconfigure UI and safe member remapping."""
from __future__ import annotations

import types
import unittest
from test_options_flow import load_flow


class ReconfigureFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module, _ = load_flow()
        self.members = [
            {
                "person_id": "stable-child",
                "person_name": "Child",
                "iphone_tracker": "device_tracker.child",
                "watch_sensor": "binary_sensor.watch_child",
                "bag_sensor": "binary_sensor.bag",
                "bag_policy": "always",
            },
            {
                "person_id": "stable-adult",
                "person_name": "Adult",
                "iphone_tracker": "device_tracker.adult",
                "watch_sensor": "binary_sensor.watch_adult",
                "bag_policy": "legacy",
            },
        ]
        self.entry = types.SimpleNamespace(data={
            "household_name": "Household",
            "people": self.members,
            "gate_entities": ["switch.gate"],
            "door_contact": "binary_sensor.door",
            "door_lock": "lock.front",
        }, options={})
        self.flow = self.module.FamilyPresenceConfigFlow()
        self.flow._reconfigure_entry = self.entry

    async def test_final_profile_blocks_configuration_changes(self):
        self.entry.options = {"output_profile": "final"}
        menu = await self.flow.async_step_reconfigure()
        self.assertEqual(menu, {"type": "abort", "reason": "shadow_required"})
        shared = await self.flow.async_step_reconfigure_shared({
            "household_name": "Changed",
        })
        self.assertEqual(shared, {"type": "abort", "reason": "shadow_required"})
        self.assertEqual(self.entry.data["household_name"], "Household")

    async def test_menu_exposes_shared_edit_add_and_remove(self):
        menu = await self.flow.async_step_reconfigure()
        self.assertEqual(menu["type"], "menu")
        self.assertEqual(
            menu["menu_options"],
            ["reconfigure_shared", "reconfigure_choose",
             "reconfigure_add", "reconfigure_remove"],
        )

    async def test_shared_sensor_unselection_clears_stored_old_mapping(self):
        result = await self.flow.async_step_reconfigure_shared({
            "household_name": "New Home",
            "gate_entities": ["switch.new_gate"],
            # Old door and lock were explicitly deselected.
        })
        self.assertTrue(result["reloaded"])
        self.assertEqual(self.entry.data["household_name"], "New Home")
        self.assertEqual(self.entry.data["gate_entities"], ["switch.new_gate"])
        self.assertIsNone(self.entry.data["door_contact"])
        self.assertIsNone(self.entry.data["door_lock"])
        self.assertEqual(self.entry.data["people"], self.members)
        self.assertEqual(self.flow._unique_id, "household")
        self.assertTrue(self.flow._checked_unique_id)

    async def test_read_only_legacy_binary_can_be_configured_or_cleared(self):
        schema = (await self.flow.async_step_reconfigure_shared())["schema"]
        self.assertIn("legacy_all_away_binary", schema)
        out = await self.flow.async_step_reconfigure_shared({
            "household_name": "Household",
            "legacy_all_away_binary": "binary_sensor.casa_certamente_vuota",
        })
        self.assertTrue(out["reloaded"])
        self.assertEqual(
            self.entry.data["legacy_all_away_binary"],
            "binary_sensor.casa_certamente_vuota",
        )
        out = await self.flow.async_step_reconfigure_shared({
            "household_name": "Household",
        })
        self.assertTrue(out["reloaded"])
        self.assertIsNone(self.entry.data["legacy_all_away_binary"])
        self.assertEqual(self.entry.data["people"], self.members)

    async def test_name_change_preserves_immutable_id(self):
        await self.flow.async_step_reconfigure_choose({"person": "stable-child"})
        result = await self.flow.async_step_reconfigure_edit({
            "person_name": "Renamed Child",
            "iphone_tracker": "device_tracker.child",
            "watch_sensor": "binary_sensor.watch_child",
            "bag_sensor": "binary_sensor.bag",
            "legacy_presence_entity": "input_select.child",
        })
        self.assertTrue(result["reloaded"])
        changed = self.entry.data["people"][0]
        self.assertEqual(changed["person_id"], "stable-child")
        self.assertEqual(changed["person_name"], "Renamed Child")
        self.assertEqual(changed["legacy_presence_entity"], "input_select.child")
        self.assertEqual(changed["bag_policy"], "always")
        self.assertEqual(self.entry.data["people"][1], self.members[1])

    async def test_edited_person_can_remove_optional_watch_sensor(self):
        await self.flow.async_step_reconfigure_choose({"person": "stable-child"})
        await self.flow.async_step_reconfigure_edit({
            "person_name": "Child", "iphone_tracker": "device_tracker.child",
        })
        person = self.entry.data["people"][0]
        self.assertNotIn("watch_sensor", person)
        self.assertNotIn("bag_sensor", person)
        self.assertEqual(person["person_id"], "stable-child")

    async def test_duplicates_and_missing_sources_are_rejected(self):
        await self.flow.async_step_reconfigure_choose({"person": "stable-child"})
        duplicate_name = await self.flow.async_step_reconfigure_edit({
            "person_name": "Adult",
            "iphone_tracker": "device_tracker.child",
        })
        self.assertEqual(duplicate_name["errors"]["person_name"], "duplicate_name")
        duplicate_sensor = await self.flow.async_step_reconfigure_edit({
            "person_name": "Child",
            "watch_sensor": "binary_sensor.watch_adult",
        })
        self.assertEqual(duplicate_sensor["errors"]["base"], "duplicate_source")
        missing = await self.flow.async_step_reconfigure_edit({
            "person_name": "Child",
        })
        self.assertEqual(missing["errors"]["base"], "missing_sources")
        self.assertEqual(self.entry.data["people"], self.members)

    async def test_add_person_does_not_modify_other_people(self):
        result = await self.flow.async_step_reconfigure_add({
            "person_name": "Guest",
            "iphone_tracker": "device_tracker.guest",
        })
        self.assertTrue(result["reloaded"])
        self.assertEqual(len(self.entry.data["people"]), 3)
        self.assertEqual(self.entry.data["people"][:2], self.members)
        guest = self.entry.data["people"][-1]
        self.assertEqual(guest["person_name"], "Guest")
        self.assertNotEqual(guest["person_id"], "stable-adult")
        self.assertNotEqual(guest["person_id"], "stable-child")

    async def test_remove_person_does_not_leave_empty_household(self):
        result = await self.flow.async_step_reconfigure_remove({
            "person": "stable-child",
        })
        self.assertTrue(result["reloaded"])
        self.assertEqual(self.entry.data["people"], [self.members[1]])
        retry = self.module.FamilyPresenceConfigFlow()
        retry._reconfigure_entry = self.entry
        menu = await retry.async_step_reconfigure()
        self.assertNotIn("reconfigure_remove", menu["menu_options"])
        blocked = await retry.async_step_reconfigure_remove()
        self.assertEqual(blocked, {"type": "abort", "reason": "last_member"})

    async def test_unknown_member_cannot_be_edited_or_removed(self):
        error = await self.flow.async_step_reconfigure_choose({"person": "fake"})
        self.assertEqual(error["errors"]["base"], "invalid_person")
        error = await self.flow.async_step_reconfigure_remove({"person": "fake"})
        self.assertEqual(error["errors"]["base"], "invalid_person")
        self.flow._edit_person_key = "fake"
        self.assertEqual(
            await self.flow.async_step_reconfigure_edit(),
            {"type": "abort", "reason": "person_not_found"},
        )

    async def test_legacy_name_based_member_upgrades_without_changing_key(self):
        self.entry.data["people"] = [{
            "person_name": "Member",
            "bag_sensor": "binary_sensor.legacy_bag",
        }]
        self.flow._edit_person_key = "member"
        result = await self.flow.async_step_reconfigure_edit({
            "person_name": "New Name",
            "bag_sensor": "binary_sensor.legacy_bag",
        })
        self.assertTrue(result["reloaded"])
        self.assertEqual(
            self.entry.data["people"][0]["person_id"], "member"
        )
        self.assertEqual(
            self.entry.data["people"][0]["person_name"], "New Name"
        )

    async def test_user_setup_refuses_duplicated_person_source(self):
        self.flow._people = [self.members[0]]
        result = await self.flow.async_step_person({
            "person_name": "Other",
            "watch_sensor": "binary_sensor.watch_child",
        })
        self.assertEqual(result["errors"]["base"], "duplicate_source")
        self.assertEqual(self.flow._people, [self.members[0]])


if __name__ == "__main__":
    unittest.main()
