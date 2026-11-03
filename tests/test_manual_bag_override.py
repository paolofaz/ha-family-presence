"""One-shot manual state changes never become persistent priority holds."""
import unittest
from datetime import datetime, timedelta, timezone

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import State, Event
from custom_components.family_presence.bag_schedule import BagSchedule, ALL_DAYS


class ManualForceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)
        self.sources = {"bag": "off", "watch": "on", "phone": "home"}

        async def immediate(_):
            return None

        self.engine = ShadowCoordinator(
            [PersonSources(
                "person", "Member", iphone="phone", watch="watch", bag="bag",
                bag_schedule=BagSchedule(True, "00:00", "00:00", ALL_DAYS),
            )],
            read_state=self.sources.get,
            clock=lambda: self.now,
            sleep=immediate,
        )

    async def test_force_home_even_with_bag_off_then_new_phone_departure(self):
        c = self.engine
        result = await c.force_state("person", State.HOME)
        self.assertEqual(result.current, State.HOME)
        self.assertEqual(c.state("person"), State.HOME)
        self.assertEqual(c.runtime["person"].state_origin, "manual_force")
        self.assertEqual(c.runtime["person"].last_reason,
                         "Forzato in casa manualmente")
        self.assertIs(c.all_away(), False)
        self.now += timedelta(minutes=30)
        self.sources["phone"] = "not_home"
        result = await c.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(result.current, State.AWAY)
        self.assertEqual(c.runtime["person"].state_origin, "observed_transition")
        self.assertIs(c.all_away(), True)

    async def test_force_away_then_new_phone_arrival(self):
        c = self.engine
        await c.force_state("person", State.AWAY)
        self.assertEqual(c.state("person"), State.AWAY)
        self.now += timedelta(seconds=3)
        self.sources["phone"] = "home"
        result = await c.process("person", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertEqual(result.current, State.HOME)

    async def test_watch_can_update_forced_away_with_normal_corroborration(self):
        c = self.engine
        await c.force_state("person", State.AWAY)
        self.now += timedelta(seconds=2)
        c.record_physical("gate", self.now)
        result = await c.process("person", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(result.current, State.HOME)

    async def test_explicit_force_has_no_bag_or_schedule_prerequisite(self):
        c = ShadowCoordinator(
            [PersonSources("adult", "Adult")], read_state=lambda _key: None,
            clock=lambda: self.now,
        )
        await c.force_state("adult", State.HOME)
        self.assertEqual(c.state("adult"), State.HOME)
        await c.force_state("adult", State.AWAY)
        self.assertEqual(c.state("adult"), State.AWAY)

    async def test_out_of_order_old_source_callback_cannot_undo_button(self):
        c = self.engine
        older = self.now - timedelta(seconds=1)
        await c.force_state("person", State.HOME)
        self.assertIsNone(await c.process(
            "person", Event.IPHONE_LEFT, event_time=older,
        ))
        self.assertEqual(c.state("person"), State.HOME)

    async def test_second_button_press_updates_reason_even_if_same_state(self):
        c = self.engine
        await c.force_state("person", State.HOME)
        self.now += timedelta(seconds=5)
        await c.force_state("person", State.HOME)
        self.assertEqual(c.runtime["person"].last_changed, self.now)

    async def test_force_is_a_single_event_stored_without_hold(self):
        c = self.engine
        await c.force_state("person", State.HOME)
        snapshot = c.snapshot()
        self.assertEqual(snapshot["format"], 4)
        self.assertEqual(snapshot["people"]["person"]["manual"]["last_action"], "manual_home")
        new = ShadowCoordinator(
            list(c.people.values()), read_state=self.sources.get,
            clock=lambda: self.now,
        )
        self.assertEqual(new.restore_snapshot(snapshot), 1)
        self.assertEqual(new.state("person"), State.HOME)
        self.assertTrue(new.runtime["person"].restored_from_storage)
        self.assertIsNone(new.all_away())
        self.now += timedelta(seconds=10)
        self.sources["phone"] = "not_home"
        await new.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(new.state("person"), State.AWAY)

    async def test_wrong_manual_target_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.engine.force_state("person", State.NEAR_HOME)


if __name__ == "__main__":
    unittest.main()
