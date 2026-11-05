"""v1.0.1: bag departure cannot be superseded by a Watch left charging at home."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import unittest

from custom_components.family_presence.bag_schedule import BagSchedule
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, Evidence, State, decide


class BagWatchHotfixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Thursday 5 November: 07:10 UTC = 08:10 in Rome.
        self.now = datetime(2026, 11, 5, 7, 10, tzinfo=timezone.utc)
        self.inputs = {"bag": "on", "watch": "off", "iphone": "home"}

        async def instant_sleep(_):
            return None

        self.sleep = instant_sleep
        self.schedule = BagSchedule(
            enabled=True, start="08:00", end="09:00", days=(3,),
        )

    def engine(self, *, schedule=None):
        return ShadowCoordinator(
            [PersonSources(
                "arianna", "Arianna", iphone="iphone",
                watch="watch", bag="bag",
                bag_schedule=schedule or self.schedule,
            )],
            read_state=self.inputs.get,
            local_timezone=ZoneInfo("Europe/Rome"),
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    async def departure(self, c):
        c.runtime["arianna"].state = State.HOME
        self.now = datetime(2026, 11, 5, 7, 20, tzinfo=timezone.utc)
        self.inputs["bag"] = "off"
        result = await c.process(
            "arianna", Event.BAG_LEFT, event_time=self.now,
        )
        self.assertEqual(result.current, State.AWAY)
        self.assertTrue(c.runtime["arianna"].bag_return_eligible)

    async def test_full_school_trip_watch_and_shared_door_cannot_confirm_return(self):
        c = self.engine()
        await self.departure(c)
        changed = c.runtime["arianna"].last_changed

        # 10:00 local: the Watch is switched on while its owner is at school.
        self.now = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
        self.inputs["watch"] = "on"
        self.assertIsNone(await c.process(
            "arianna", Event.WATCH_SEEN, event_time=self.now,
        ))
        self.assertEqual(c.state("arianna"), State.AWAY)
        self.assertEqual(c.runtime["arianna"].last_changed, changed)
        self.assertTrue(c.runtime["arianna"].bag_return_eligible)

        # Another member opens the shared door immediately afterward.
        self.now += timedelta(seconds=12)
        c.record_physical("door_open", self.now)
        self.assertIsNone(await c.process(
            "arianna", Event.PHYSICAL_ENTRY,
            event_time=self.now, physical_kind="door_open",
        ))
        self.assertEqual(c.state("arianna"), State.AWAY)
        self.assertTrue(c.all_away())

        # At 13:00 local, a real OFF -> ON of the bag can still return HOME:
        # the 08:00-09:00 schedule applies ONLY to the departure.
        self.now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        self.inputs["bag"] = "on"
        result = await c.process(
            "arianna", Event.BAG_ARRIVED, event_time=self.now,
        )
        self.assertEqual(result.current, State.HOME)
        self.assertFalse(c.runtime["arianna"].bag_return_eligible)

    async def test_real_iphone_arrival_can_override_bag_trip(self):
        c = self.engine()
        await self.departure(c)
        self.now += timedelta(minutes=37)
        self.inputs["iphone"] = "home"
        result = await c.process(
            "arianna", Event.IPHONE_ARRIVED, event_time=self.now,
        )
        self.assertEqual(result.current, State.HOME)
        self.assertFalse(c.runtime["arianna"].bag_return_eligible)

    async def test_manual_home_can_override_bag_trip(self):
        c = self.engine()
        await self.departure(c)
        self.now += timedelta(seconds=2)
        result = await c.force_state("arianna", State.HOME)
        self.assertEqual(result.current, State.HOME)
        self.assertFalse(c.runtime["arianna"].bag_return_eligible)

    async def test_legacy_snapshot_near_home_with_bag_origin_becomes_away(self):
        c = self.engine()
        await self.departure(c)
        c.runtime["arianna"].state = State.NEAR_HOME
        c.runtime["arianna"].last_reason = "Watch detected near home"
        snapshot = c.snapshot()

        self.now += timedelta(hours=2)
        restored = self.engine()
        self.assertEqual(restored.restore_snapshot(snapshot), 1)
        rt = restored.runtime["arianna"]
        self.assertEqual(rt.state, State.AWAY)
        self.assertTrue(rt.bag_return_eligible)
        self.assertTrue(rt.restored_from_storage)
        self.assertIn("Uscita zaino ancora attiva", rt.last_reason)
        self.assertEqual(rt.last_changed, self.now)
        self.assertTrue(restored.all_away())
        self.assertEqual(restored._physical, {})

        self.now += timedelta(seconds=2)
        self.inputs["watch"] = "on"
        self.assertIsNone(await restored.process(
            "arianna", Event.WATCH_SEEN, event_time=self.now,
        ))
        self.assertTrue(rt.bag_return_eligible)
        self.now += timedelta(seconds=1)
        self.inputs["bag"] = "on"
        self.assertEqual((await restored.process(
            "arianna", Event.BAG_ARRIVED, event_time=self.now,
        )).current, State.HOME)

    async def test_restore_without_confirmed_bag_off_remains_conservative(self):
        c = self.engine()
        await self.departure(c)
        c.runtime["arianna"].state = State.NEAR_HOME
        snapshot = c.snapshot()
        for bag_state in ("on", "unavailable", "unknown"):
            self.inputs["bag"] = bag_state
            restored = self.engine()
            self.assertEqual(restored.restore_snapshot(snapshot), 1)
            self.assertEqual(restored.state("arianna"), State.NEAR_HOME)
            self.assertTrue(restored.runtime["arianna"].bag_return_eligible)

    async def test_snapshot_without_provenance_does_not_change_near_home(self):
        c = self.engine()
        await self.departure(c)
        c.runtime["arianna"].state = State.NEAR_HOME
        c.runtime["arianna"].bag_return_eligible = False
        restored = self.engine()
        self.assertEqual(restored.restore_snapshot(c.snapshot()), 1)
        self.assertEqual(restored.state("arianna"), State.NEAR_HOME)

    async def test_disabled_bag_does_not_assert_old_priority(self):
        c = self.engine()
        await self.departure(c)
        c.runtime["arianna"].state = State.NEAR_HOME
        disabled = BagSchedule(False, "08:00", "09:00", (3,))
        restored = self.engine(schedule=disabled)
        self.assertEqual(restored.restore_snapshot(c.snapshot()), 1)
        self.assertFalse(restored.runtime["arianna"].bag_return_eligible)
        self.assertEqual(restored.state("arianna"), State.NEAR_HOME)

    async def test_diagnostic_does_not_report_expected_home_devices_as_errors(self):
        c = self.engine()
        await self.departure(c)
        self.inputs["watch"] = "on"
        assessment = c.household_assessment()
        self.assertEqual(assessment.source_warnings, {})

        # No causal departure: the identical phone+Watch readings are suspect.
        c.runtime["arianna"].bag_return_eligible = False
        warnings = c.household_assessment().source_warnings["arianna"]
        self.assertIn("iphone_home_con_fsm_away", warnings)
        self.assertIn("watch_on_con_fsm_away", warnings)

        # An unavailable bag remains diagnostic even with valid provenance.
        c.runtime["arianna"].bag_return_eligible = True
        self.inputs["bag"] = "unavailable"
        warnings = c.household_assessment().source_warnings["arianna"]
        self.assertIn("zaino_non_disponibile", warnings)

    async def test_pure_rules_defensively_block_watch_and_gate_with_bag_origin(self):
        for state in (State.AWAY, State.NEAR_HOME):
            for event in (Event.WATCH_SEEN, Event.PHYSICAL_ENTRY):
                result = decide(
                    state, event,
                    Evidence(watch_detected=True, door_open_entry=True,
                             gate_entry=True),
                    bag_return_eligible=True,
                )
                self.assertIsNone(result)
        # Without an accepted bag departure, the established logic still works.
        self.assertEqual(decide(
            State.AWAY, Event.WATCH_SEEN, Evidence(),
            bag_return_eligible=False,
        ).state, State.NEAR_HOME)


if __name__ == "__main__":
    unittest.main()
