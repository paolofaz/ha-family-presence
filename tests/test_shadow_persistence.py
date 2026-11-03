"""Shadow-owned persistence: legacy YAML is a read-only comparison source."""
import unittest
from datetime import datetime, timezone

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import BagPolicy, Event, State


class ShadowPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.time = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
        self.values = {
            "bag": "on", "watch": "on", "phone": "home",
            "reference": "home", "another_ref": "away",
        }

        async def instant_delay(_):
            return None
        self.sleep = instant_delay

    def new(self, *, iphone="phone", reference="reference",
            bag_policy=BagPolicy.ALWAYS):
        return ShadowCoordinator(
            [PersonSources(
                key="child", name="Child", iphone=iphone, watch="watch",
                bag="bag", reference=reference, bag_policy=bag_policy,
            )],
            read_state=self.values.get,
            clock=lambda: self.time,
            sleep=self.sleep,
        )

    async def outside(self):
        c = self.new()
        d = await c.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertEqual(d.current, State.AWAY)
        return c

    async def test_start_never_uses_legacy_helper_without_snapshot(self):
        for baseline in ("home", "away", "near_home", "unavailable"):
            with self.subTest(baseline=baseline):
                self.values["reference"] = baseline
                c = self.new()
                self.assertIsNone(c.state("child"))
                self.assertIsNone(c.runtime["child"].last_reason)
                self.assertEqual(c.runtime["child"].state_origin, "unknown")
                self.assertIsNone(c.all_away())
                await c.reconcile()
                self.assertIsNone(c.state("child"))  # Bag ON proves no state.

    async def test_own_state_reason_survive_disagreeing_yaml_restart(self):
        first = await self.outside()
        snapshot = first.snapshot()
        original_time = first.runtime["child"].last_changed
        self.assertEqual(snapshot["format"], 3)
        self.values["reference"] = "home"  # YAML DISAGREES.
        restarted = self.new()
        self.assertIsNone(restarted.state("child"))
        self.assertEqual(restarted.restore_snapshot(snapshot), 1)
        self.assertEqual(restarted.state("child"), State.AWAY)
        self.assertEqual(restarted.runtime["child"].last_reason, "iPhone left home zone")
        self.assertEqual(restarted.runtime["child"].last_changed, original_time)
        self.assertEqual(restarted.runtime["child"].state_origin, "saved_shadow_unverified")
        self.assertEqual(restarted.runtime["child"].reason_origin, "saved_snapshot_unverified")
        self.assertTrue(restarted.runtime["child"].restored_from_storage)
        self.assertIsNone(restarted.all_away())
        await restarted.reconcile()
        self.assertEqual(restarted.state("child"), State.AWAY)
        self.assertEqual(restarted.runtime["child"].last_reason, "iPhone left home zone")

    async def test_same_state_reason_survives_multiple_restart_cycles(self):
        first = await self.outside()
        saved = first.snapshot()
        for reference in ("home", "away", "unavailable", "near_home"):
            self.values["reference"] = reference
            next_run = self.new()
            self.assertEqual(next_run.restore_snapshot(saved), 1)
            self.assertEqual(next_run.state("child"), State.AWAY)
            self.assertEqual(next_run.runtime["child"].last_reason, "iPhone left home zone")
            saved = next_run.snapshot()
        self.assertEqual(saved["format"], 3)

    async def test_changing_only_comparison_helper_preserves_new_format(self):
        first = await self.outside()
        saved = first.snapshot()
        self.assertEqual(saved["format"], 3)
        other_reference = self.new(reference="another_ref")
        self.assertEqual(other_reference.restore_snapshot(saved), 1)
        self.assertEqual(other_reference.state("child"), State.AWAY)
        self.assertEqual(other_reference.runtime["child"].last_reason, "iPhone left home zone")

    async def test_alpha3_format_one_snapshot_migrates_without_yaml_seeding(self):
        first = await self.outside()
        saved = first.snapshot()
        saved["format"] = 1
        saved["people"]["child"]["fingerprint"] = first._fingerprint(
            first.people["child"], legacy=True
        )
        self.values["reference"] = "home"
        upgraded = self.new()
        self.assertEqual(upgraded.restore_snapshot(saved), 1)
        self.assertEqual(upgraded.state("child"), State.AWAY)
        self.assertEqual(upgraded.runtime["child"].last_reason, "iPhone left home zone")
        self.assertEqual(upgraded.snapshot()["format"], 2)

    async def test_changed_source_or_priority_rejects_stale_snapshot(self):
        first = await self.outside()
        saved = first.snapshot()
        new_source = self.new(iphone="new_phone")
        self.assertEqual(new_source.restore_snapshot(saved), 0)
        self.assertIsNone(new_source.state("child"))
        new_policy = self.new(bag_policy=BagPolicy.LEGACY)
        self.assertEqual(new_policy.restore_snapshot(saved), 0)
        self.assertIsNone(new_policy.state("child"))

    async def test_stale_snapshot_cannot_make_all_away_true(self):
        initial = await self.outside()
        self.values["reference"] = "away"
        restored = self.new()
        self.assertEqual(restored.restore_snapshot(initial.snapshot()), 1)
        self.assertIsNone(restored.all_away())
        self.values["bag"] = "off"
        await restored.process("child", Event.RECONCILE, event_time=self.time)
        self.assertIsNone(restored.all_away())
        self.values["phone"] = "home"
        await restored.process("child", Event.IPHONE_ARRIVED, event_time=self.time)
        self.assertIsNone(restored.all_away())  # Bag veto blocks false HOME.
        self.values["bag"] = "on"
        await restored.process("child", Event.BAG_ARRIVED, event_time=self.time)
        self.assertIs(restored.all_away(), False)
        self.values["phone"] = "not_home"
        await restored.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertIs(restored.all_away(), True)

    async def test_near_home_duration_is_not_fabricated_after_reboot(self):
        first = await self.outside()
        self.values["phone"] = "not_home"
        result = await first.process("child", Event.WATCH_SEEN, event_time=self.time)
        self.assertEqual(result.current, State.NEAR_HOME)
        restarted = self.new()
        self.assertEqual(restarted.restore_snapshot(first.snapshot()), 1)
        self.assertEqual(restarted.state("child"), State.NEAR_HOME)
        self.assertIsNone(restarted.near_home_age_seconds("child"))
        self.assertEqual(restarted.pending_near_home(min_seconds=100), [])

    async def test_old_physical_events_never_reused(self):
        first = await self.outside()
        first.record_physical("gate", self.time)
        restarted = self.new()
        self.assertEqual(restarted.restore_snapshot(first.snapshot()), 1)
        self.assertEqual(restarted._physical, {})
        self.values["phone"] = "not_home"
        result = await restarted.process("child", Event.WATCH_SEEN, event_time=self.time)
        self.assertEqual(result.current, State.NEAR_HOME)

    async def test_missing_prior_reason_is_not_invented(self):
        original = self.new()
        await original.process("child", Event.IPHONE_LEFT, event_time=self.time)
        saved = original.snapshot()
        saved["people"]["child"]["reason"] = None
        saved["people"]["child"]["last_changed"] = "bad_timestamp"
        c = self.new()
        self.assertEqual(c.restore_snapshot(saved), 1)
        self.assertEqual(c.state("child"), State.AWAY)
        self.assertIsNone(c.runtime["child"].last_reason)
        self.assertIsNone(c.runtime["child"].last_changed)
        self.assertEqual(c.runtime["child"].reason_origin, "not_recorded")

    async def test_malformed_snapshots_are_ignored_without_copying_yaml(self):
        self.values["reference"] = "home"
        c = self.new()
        for case in [
            None, {}, {"format": 999, "people": {}},
            {"format": 2, "people": []},
            {"format": 2, "people": {"child": "away"}},
        ]:
            with self.subTest(case=case):
                self.assertEqual(c.restore_snapshot(case), 0)
                self.assertIsNone(c.state("child"))

    async def test_legacy_v1_comparator_change_can_only_skip_old_snapshot(self):
        c = await self.outside()
        saved = c.snapshot()
        saved["format"] = 1
        saved["people"]["child"]["fingerprint"] = c._fingerprint(
            c.people["child"], legacy=True
        )
        swapped = self.new(reference="another_ref")
        self.assertEqual(swapped.restore_snapshot(saved), 0)
        self.assertIsNone(swapped.state("child"))

    async def test_listeners_see_transitions_and_comparator_refresh(self):
        c = self.new()
        noticed = []
        unsubscribe = c.async_add_listener(noticed.append)
        c.notify_source_update("child")
        self.assertEqual(noticed, ["child"])
        await c.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertEqual(noticed, ["child", "child"])
        unsubscribe()
        c.notify_source_update("child")
        self.assertEqual(len(noticed), 2)

    async def test_snapshot_never_persists_ble_data_or_reference_value(self):
        c = self.new()
        snapshot = c.snapshot()
        serialized = str(snapshot)
        for secret in ("last_seen", "rssi", "irk", "another_ref", "phone_value"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(snapshot["format"], 3)


if __name__ == "__main__":
    unittest.main()
