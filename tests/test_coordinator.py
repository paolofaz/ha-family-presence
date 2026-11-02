"""Tests for read-only coordinator, no HA installation necessary."""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from custom_components.family_presence.coordinator import (
    PersonSources, ShadowCoordinator, bag_status, parse_state,
)
from custom_components.family_presence.fsm import BagPolicy, BagStatus, Event, State


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
        self.inputs = {"bag": "off", "watch": "on", "phone": "not_home", "ref": "away"}

        async def instant_sleep(seconds):
            return None

        self.sleep = instant_sleep

    def engine(self, *, policy=BagPolicy.ALWAYS, reference="ref", people=None):
        return ShadowCoordinator(
            people or [PersonSources(
                key="child", name="Child", iphone="phone", watch="watch",
                bag="bag", reference=reference, bag_policy=policy,
            )],
            read_state=lambda key: self.inputs.get(key),
            clock=lambda: self.now,
            sleep=self.sleep,
            local_timezone=ZoneInfo("Europe/Rome"),
        )

    async def test_bag_absent_wins_over_neighbor_gate_and_watch(self):
        c = self.engine()
        c.record_physical("gate", self.now - timedelta(seconds=5))
        await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(c.state("child"), State.AWAY)
        self.assertEqual(c.runtime["child"].last_blocked_event, Event.WATCH_SEEN)
        await c.process("child", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertEqual(c.state("child"), State.AWAY)

    async def test_bag_arrived_goes_home_but_presence_does_not_stay_locked(self):
        c = self.engine()
        self.inputs["bag"] = "on"
        d = await c.process("child", Event.BAG_ARRIVED, event_time=self.now)
        self.assertEqual((d.current, d.reason), (State.HOME, "Bag arrived"))
        d = await c.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(d.current, State.AWAY)

    async def test_bag_absent_reconcile_after_restart(self):
        self.inputs.pop("ref")
        c = self.engine()
        self.assertIsNone(c.state("child"))
        decisions = await c.reconcile()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(c.state("child"), State.AWAY)
        self.assertEqual(decisions[0].reason, "Bag absent (priority)")
        self.inputs["bag"] = "unavailable"
        c2 = self.engine()
        self.assertEqual(await c2.reconcile(), [])
        self.assertIsNone(c2.state("child"))

    async def test_unknown_bag_does_not_veto_entry(self):
        self.inputs.update({"bag": "unavailable", "phone": "home"})
        c = self.engine()
        c.record_physical("door_open", self.now)
        d = await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(d.current, State.HOME)

    async def test_watch_off_uses_last_seen_not_receipt_time(self):
        self.inputs.update({"bag": "on", "ref": "home", "phone": "home", "watch": "off"})
        c = self.engine()
        self.now = self.now.replace(minute=10)
        c.record_physical("gate", self.now - timedelta(minutes=3))
        d = await c.process(
            "child", Event.WATCH_LOST, event_time=self.now,
            last_seen_before_off=self.now - timedelta(minutes=1, seconds=10),
        )
        self.assertEqual(d.current, State.AWAY)
        self.assertEqual(d.reason, "Watch OFF + recent gate before last_seen")

    async def test_watch_off_without_last_seen_has_no_physical_evidence(self):
        self.inputs.update({"bag": "on", "ref": "home", "phone": "home", "watch": "off"})
        c = self.engine()
        c.record_physical("gate", self.now - timedelta(seconds=5))
        self.assertIsNone(await c.process("child", Event.WATCH_LOST, event_time=self.now))
        self.assertEqual(c.state("child"), State.HOME)

    async def test_legacy_departure_uses_local_school_window(self):
        self.inputs["ref"] = "home"
        c = self.engine(policy=BagPolicy.LEGACY)
        # 08:00 UTC = 09:00 Europe/Rome in November.
        self.assertEqual(
            (await c.process("child", Event.BAG_LEFT, event_time=self.now)).current,
            State.AWAY,
        )
        self.now = self.now.replace(hour=11)
        c2 = self.engine(policy=BagPolicy.LEGACY)
        self.assertIsNone(await c2.process("child", Event.BAG_LEFT, event_time=self.now))
        self.assertEqual(c2.state("child"), State.HOME)

    async def test_newer_bag_update_cancels_pending_watch_on(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def held_delay(seconds):
            started.set()
            await release.wait()

        self.sleep = held_delay
        self.inputs["bag"] = "on"
        c = self.engine()
        old_version = c.note_person_event("child")
        task = asyncio.create_task(c.process(
            "child", Event.WATCH_SEEN, event_time=self.now, revision=old_version,
        ))
        await started.wait()
        self.inputs["bag"] = "off"
        new_version = c.note_person_event("child")
        release.set()
        self.assertIsNone(await task)
        await c.process("child", Event.BAG_LEFT, event_time=self.now, revision=new_version)
        self.assertEqual(c.state("child"), State.AWAY)

    async def test_all_away_requires_every_member_known(self):
        self.inputs = {"p1_ref": "away", "p2_ref": "home", "p1_bag": "off", "p2_bag": "on"}
        people = [
            PersonSources("p1", "Person 1", bag="p1_bag", reference="p1_ref"),
            PersonSources("p2", "Person 2", bag="p2_bag", reference="p2_ref"),
        ]
        c = self.engine(people=people)
        self.assertIs(c.all_away(), False)
        await c.process("p2", Event.IPHONE_LEFT, event_time=self.now)
        self.assertIs(c.all_away(), True)
        unknown = self.engine(people=[PersonSources("p1", "One"), PersonSources("p2", "Two")])
        self.assertIsNone(unknown.all_away())

    def test_input_status_classification(self):
        self.assertEqual(bag_status("off", True), BagStatus.ABSENT)
        self.assertEqual(bag_status("on", True), BagStatus.PRESENT)
        self.assertEqual(bag_status("unavailable", True), BagStatus.UNKNOWN)
        self.assertEqual(bag_status("off", False), BagStatus.NOT_CONFIGURED)
        self.assertIsNone(parse_state("unknown"))


if __name__ == "__main__":
    unittest.main()
