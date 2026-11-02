"""Shadow state persistence and notification contracts, without HA imports."""
import unittest
from datetime import datetime, timedelta, timezone

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import BagPolicy, Event, State


class ShadowPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.time = datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)
        self.values = {"bag": "on", "watch": "on", "phone": "home", "reference": "home"}

        async def instant_delay(_):
            return None
        self.sleep = instant_delay

    def new(self, *, iphone="phone", reference="reference", bag_policy=BagPolicy.ALWAYS):
        return ShadowCoordinator(
            [PersonSources(
                key="child", name="Child", iphone=iphone, watch="watch",
                bag="bag", reference=reference, bag_policy=bag_policy,
            )],
            read_state=self.values.get,
            clock=lambda: self.time,
            sleep=self.sleep,
        )

    async def test_restarts_use_live_yaml_when_available(self):
        first = self.new()
        await first.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertEqual(first.state("child"), State.AWAY)
        saved = first.snapshot()
        # YAML still says HOME. It takes priority over cached shadow state on restart.
        new = self.new()
        self.assertEqual(new.restore_snapshot(saved), 0)
        self.assertEqual(new.state("child"), State.HOME)
        self.assertFalse(new.runtime["child"].restored_from_storage)

    async def test_restore_when_reference_unavailable_but_mapping_same(self):
        first = self.new()
        await first.process("child", Event.IPHONE_LEFT, event_time=self.time)
        saved = first.snapshot()
        self.values["reference"] = "unavailable"
        second = self.new()
        self.assertEqual(second.restore_snapshot(saved), 1)
        self.assertEqual(second.state("child"), State.AWAY)
        self.assertTrue(second.runtime["child"].restored_from_storage)
        self.assertIsNotNone(second.runtime["child"].last_changed)
        # A real transition clears the restored marker.
        await second.process("child", Event.IPHONE_ARRIVED, event_time=self.time)
        self.assertEqual(second.state("child"), State.HOME)
        self.assertFalse(second.runtime["child"].restored_from_storage)

    async def test_changed_source_mapping_rejects_persisted_state(self):
        first = self.new()
        await first.process("child", Event.IPHONE_LEFT, event_time=self.time)
        saved = first.snapshot()
        self.values.pop("reference")
        new = self.new(iphone="different_phone")
        self.assertEqual(new.restore_snapshot(saved), 0)
        self.assertIsNone(new.state("child"))
        changed_policy = self.new(bag_policy=BagPolicy.LEGACY)
        self.assertEqual(changed_policy.restore_snapshot(saved), 0)

    async def test_restored_away_does_not_establish_house_empty(self):
        initial = self.new()
        await initial.process("child", Event.IPHONE_LEFT, event_time=self.time)
        saved = initial.snapshot()
        self.values["reference"] = "unavailable"
        restored = self.new()
        self.assertEqual(restored.restore_snapshot(saved), 1)
        self.assertEqual(restored.state("child"), State.AWAY)
        self.assertIsNone(restored.all_away())  # Stale snapshot cannot arm alarm.

        # A fresh observed transition clears the restored-only quality marker.
        self.values["bag"] = "off"
        await restored.process("child", Event.RECONCILE, event_time=self.time)
        # State was already AWAY; no new trusted transition was observed.
        self.assertIsNone(restored.all_away())
        self.values["phone"] = "home"
        # Bag OFF prevents false HOME and cannot clear stale state.
        await restored.process("child", Event.IPHONE_ARRIVED, event_time=self.time)
        self.assertIsNone(restored.all_away())
        # A genuine OFF->ON bag arrival is accepted as fresh HOME evidence.
        self.values["bag"] = "on"
        await restored.process("child", Event.BAG_ARRIVED, event_time=self.time)
        self.assertIs(restored.all_away(), False)
        self.values["phone"] = "not_home"
        await restored.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertIs(restored.all_away(), True)

    async def test_near_home_snapshot_has_unknown_age_after_restart(self):
        self.values["reference"] = "away"
        first = self.new()
        self.values["phone"] = "not_home"
        result = await first.process("child", Event.WATCH_SEEN, event_time=self.time)
        self.assertEqual(result.current, State.NEAR_HOME)
        saved = first.snapshot()
        self.values["reference"] = "unavailable"
        restarted = self.new()
        self.assertEqual(restarted.restore_snapshot(saved), 1)
        self.assertEqual(restarted.state("child"), State.NEAR_HOME)
        self.assertIsNone(restarted.near_home_age_seconds("child"))
        self.assertEqual(restarted.pending_near_home(min_seconds=100), [])

    async def test_old_door_and_gate_evidence_never_restore(self):
        self.values["reference"] = "away"
        first = self.new()
        first.record_physical("gate", self.time)
        saved = first.snapshot()
        self.values["reference"] = "unknown"
        restarted = self.new()
        restarted.restore_snapshot(saved)
        self.assertEqual(restarted._physical, {})
        self.values["phone"] = "not_home"
        result = await restarted.process("child", Event.WATCH_SEEN, event_time=self.time)
        self.assertEqual(result.current, State.NEAR_HOME)

    async def test_malformed_storage_never_claims_presence(self):
        self.values.pop("reference")
        c = self.new()
        cases = [None, {}, {"format": 999, "people": {}},
                 {"format": 1, "people": []},
                 {"format": 1, "people": {"child": "home"}}]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(c.restore_snapshot(case), 0)
                self.assertIsNone(c.state("child"))

    async def test_listeners_receive_transitions_and_source_updates(self):
        c = self.new()
        received = []
        unsubscribe = c.async_add_listener(received.append)
        c.notify_source_update("child")
        self.assertEqual(received, ["child"])
        await c.process("child", Event.IPHONE_LEFT, event_time=self.time)
        self.assertEqual(received, ["child", "child"])
        unsubscribe()
        c.notify_source_update("child")
        self.assertEqual(len(received), 2)

    async def test_snapshot_contains_no_raw_ble_or_phone_readings(self):
        c = self.new()
        serialized = str(c.snapshot())
        self.assertNotIn("last_seen", serialized)
        self.assertNotIn("rssi", serialized)
        self.assertNotIn("irk", serialized)
        self.assertEqual(c.snapshot()["format"], 1)


if __name__ == "__main__":
    unittest.main()
