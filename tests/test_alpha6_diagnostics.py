"""Alpha 6: event diagnostics and shadow/YAML comparison are read-only."""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from custom_components.family_presence.bag_schedule import BagSchedule, ALL_DAYS
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State


class Alpha6DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc)
        self.states = {"bag": "off", "phone": "home", "legacy": "home"}

    def new(self, *, schedule=BagSchedule()):
        return ShadowCoordinator(
            [PersonSources("child", "Child", iphone="phone", bag="bag",
                           reference="legacy", bag_schedule=schedule)],
            read_state=self.states.get,
            clock=lambda: self.now,
            local_timezone=ZoneInfo("Europe/Rome"),
        )

    async def test_out_of_window_bag_departure_is_explained_without_changing_home(self):
        engine = self.new()
        engine.runtime["child"].state = State.HOME
        decision = await engine.process("child", Event.BAG_LEFT, event_time=self.now)
        self.assertIsNone(decision)
        self.assertEqual(engine.state("child"), State.HOME)
        rt = engine.runtime["child"]
        self.assertEqual(rt.last_ignored_event, Event.BAG_LEFT)
        self.assertIn("fuori dalla fascia", rt.last_ignored_reason)
        self.assertEqual(rt.ignored_count, 1)
        self.assertEqual(len(rt.recent_events), 1)
        self.assertEqual(rt.recent_events[0]["outcome"], "ignored")

    async def test_disabled_bag_explains_both_events_without_changing_presence(self):
        schedule = BagSchedule(False, "00:00", "00:00", ALL_DAYS)
        engine = self.new(schedule=schedule)
        engine.runtime["child"].state = State.AWAY
        self.states["bag"] = "on"
        await engine.process("child", Event.BAG_ARRIVED, event_time=self.now)
        self.assertEqual(engine.state("child"), State.AWAY)
        self.assertIn("disabilitato", engine.runtime["child"].last_ignored_reason)

    async def test_recent_events_are_bounded_and_never_control_state(self):
        engine = self.new()
        engine.runtime["child"].state = State.HOME
        for i in range(20):
            self.now += timedelta(seconds=1)
            await engine.process("child", Event.BAG_LEFT, event_time=self.now)
        self.assertEqual(len(engine.runtime["child"].recent_events), 12)
        self.assertEqual(engine.runtime["child"].ignored_count, 20)
        self.assertEqual(engine.state("child"), State.HOME)

    async def test_mismatch_tracks_legacy_changes_and_resolves(self):
        engine = self.new()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(engine.runtime["child"].comparison_status, "diverged")
        self.assertEqual(engine.runtime["child"].divergence_since, self.now)

        self.now += timedelta(seconds=42)
        self.states["legacy"] = "away"
        engine.notify_source_update("child")
        self.assertEqual(engine.runtime["child"].comparison_status, "aligned")
        self.assertIsNone(engine.runtime["child"].divergence_since)

        self.now += timedelta(seconds=7)
        self.states["legacy"] = "home"
        engine.notify_source_update("child")
        self.assertEqual(engine.runtime["child"].comparison_status, "diverged")
        self.assertEqual(engine.runtime["child"].divergence_since, self.now)

    async def test_ignored_diagnostic_survives_restart_without_generating_an_arrival(self):
        first = self.new()
        await first.process("child", Event.BAG_LEFT, event_time=self.now)
        snapshot = first.snapshot()
        self.assertEqual(snapshot["format"], 5)
        second = self.new(schedule=BagSchedule(True, "00:00", "00:00", ALL_DAYS))
        self.assertEqual(second.restore_snapshot(snapshot), 0)  # Unknown state not restored.
        await first.force_state("child", State.HOME)
        snapshot = first.snapshot()
        second = self.new(schedule=BagSchedule(True, "00:00", "00:00", ALL_DAYS))
        self.assertEqual(second.restore_snapshot(snapshot), 1)
        self.assertEqual(second.state("child"), State.HOME)
        self.assertEqual(second.runtime["child"].last_ignored_event, Event.BAG_LEFT)
        self.assertEqual(second.runtime["child"].ignored_count, 1)
        self.assertEqual([ev["outcome"] for ev in second.runtime["child"].recent_events],
                         ["ignored", "applied"])
        await second.reconcile()
        self.assertEqual(second.state("child"), State.HOME)


if __name__ == "__main__":
    unittest.main()
