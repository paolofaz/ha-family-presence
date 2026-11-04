"""Tests for read-only coordinator, no HA installation necessary."""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from custom_components.family_presence.coordinator import (
    PersonSources, ShadowCoordinator, bag_status, parse_state,
)
from custom_components.family_presence.fsm import BagPolicy, BagStatus, Event, State
from custom_components.family_presence.bag_schedule import legacy_schedule


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
        self.inputs = {"bag": "off", "watch": "on", "phone": "not_home", "ref": "away"}

        async def instant_sleep(seconds):
            return None

        self.sleep = instant_sleep

    def engine(self, *, policy=BagPolicy.ALWAYS, reference="ref", people=None):
        specs = people or [PersonSources(
            key="child", name="Child", iphone="phone", watch="watch",
            bag="bag", reference=reference, bag_policy=policy,
            bag_schedule=legacy_schedule(policy.value),
        )]
        coordinator = ShadowCoordinator(
            specs,
            read_state=lambda key: self.inputs.get(key),
            clock=lambda: self.now,
            sleep=self.sleep,
            local_timezone=ZoneInfo("Europe/Rome"),
        )
        # Explicit test-fixture precondition: old tests exercise transitions
        # from an assumed state. PRODUCTION NEVER reads YAML to seed the FSM.
        for p in specs:
            seed = parse_state(self.inputs.get(p.reference)) if p.reference else None
            if seed is not None:
                coordinator.runtime[p.key].state = seed
                coordinator.runtime[p.key].state_origin = "test_fixture"
        return coordinator

    async def test_new_coordinator_never_reads_legacy_helper_for_state(self):
        readings = {"ref": "home", "bag": "on", "phone": "not_home"}
        engine = ShadowCoordinator(
            [PersonSources("test", "Member", iphone="phone", bag="bag", reference="ref")],
            read_state=readings.get,
            clock=lambda: self.now,
            sleep=self.sleep,
        )
        self.assertIsNone(engine.state("test"))
        self.assertIs(engine.all_away(), False)
        readings["ref"] = "away"
        engine.notify_source_update("test")
        self.assertIsNone(engine.state("test"))
        await engine.process("test", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(engine.state("test"), State.AWAY)
        readings["ref"] = "home"
        self.assertEqual(engine.state("test"), State.AWAY)

    async def test_bag_absent_does_not_override_later_phone_or_watch(self):
        c = self.engine()
        c.record_physical("gate", self.now - timedelta(seconds=5))
        result = await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(result.current, State.HOME)
        await c.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(c.state("child"), State.AWAY)
        result = await c.process("child", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertEqual(result.current, State.HOME)
    async def test_bag_arrived_goes_home_but_presence_does_not_stay_locked(self):
        c = self.engine()
        self.inputs["bag"] = "on"
        d = await c.process("child", Event.BAG_ARRIVED, event_time=self.now)
        self.assertEqual((d.current, d.reason), (State.HOME, "Bag arrived"))
        d = await c.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(d.current, State.AWAY)

    async def test_restart_with_bag_off_does_not_synthesize_exit(self):
        self.inputs.pop("ref")
        c = self.engine()
        self.assertIsNone(c.state("child"))
        self.assertEqual(await c.reconcile(), [])
        self.assertIsNone(c.state("child"))
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

    async def test_bag_departure_uses_configured_local_window(self):
        self.inputs["ref"] = "home"
        c = self.engine(policy=BagPolicy.LEGACY)
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
        self.assertIs(unknown.all_away(), False)

    async def test_queued_old_bag_off_cannot_override_later_phone_home(self):
        c = self.engine()
        c.runtime["child"].state = State.AWAY
        c.record_physical("gate", self.now)
        self.inputs["bag"] = "off"
        await c.process("child", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertEqual(c.state("child"), State.HOME)
        prior_off = self.now - timedelta(seconds=1)
        self.assertIsNone(
            await c.process("child", Event.BAG_LEFT, event_time=prior_off)
        )
        self.assertEqual(c.state("child"), State.HOME)

    async def test_near_home_is_provisional_not_home_or_away(self):
        self.inputs.update({"bag": "on", "ref": "away", "phone": "not_home"})
        c = self.engine()
        result = await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(result.current, State.NEAR_HOME)
        self.assertEqual(c.state("child"), State.NEAR_HOME)
        self.assertIs(c.all_away(), False)
        self.assertEqual(c.near_home_age_seconds("child"), 0.0)
        self.now += timedelta(minutes=31)
        self.assertEqual(c.pending_near_home(min_seconds=1800), ["child"])
        self.assertEqual(c.state("child"), State.NEAR_HOME)  # NO automatic timeout.
        self.assertEqual(c.near_home_age_seconds("child"), 31 * 60)

    async def test_near_home_can_confirm_home_with_physical_event(self):
        self.inputs.update({"bag": "on", "ref": "away", "phone": "not_home"})
        c = self.engine()
        await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.now += timedelta(seconds=25)
        c.record_physical("door_open", self.now)
        result = await c.process(
            "child", Event.PHYSICAL_ENTRY,
            event_time=self.now, physical_kind="door_open",
        )
        self.assertEqual(result.current, State.HOME)
        self.assertEqual(result.near_home_duration_seconds, 25.0)
        self.assertIsNone(c.near_home_age_seconds("child"))
        self.assertEqual(c.pending_near_home(min_seconds=0), [])

    async def test_near_home_watch_lost_returns_away(self):
        self.inputs.update({"bag": "on", "ref": "away", "phone": "not_home"})
        c = self.engine()
        await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.now += timedelta(seconds=44)
        self.inputs["watch"] = "off"
        result = await c.process("child", Event.WATCH_LOST, event_time=self.now)
        self.assertEqual(result.current, State.AWAY)
        self.assertEqual(result.near_home_duration_seconds, 44.0)
        self.assertEqual(c.all_away(), True)

    async def test_imported_near_home_has_unknown_age(self):
        self.inputs.update({"bag": "on", "ref": "near_home"})
        c = self.engine()
        self.assertEqual(c.state("child"), State.NEAR_HOME)
        self.assertIsNone(c.near_home_age_seconds("child"))
        self.now += timedelta(hours=3)
        self.assertEqual(c.pending_near_home(min_seconds=1), [])
        self.assertIs(c.all_away(), False)

    async def test_phone_arrival_confirms_near_home_without_bag_lock(self):
        self.inputs.update({"bag": "on", "ref": "away", "phone": "not_home"})
        c = self.engine()
        await c.process("child", Event.WATCH_SEEN, event_time=self.now)
        self.now += timedelta(seconds=12)
        self.inputs["phone"] = "home"
        result = await c.process("child", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertEqual(result.current, State.HOME)
        self.assertEqual(result.near_home_duration_seconds, 12)

    def test_input_status_classification(self):
        self.assertEqual(bag_status("off", True), BagStatus.ABSENT)
        self.assertEqual(bag_status("on", True), BagStatus.PRESENT)
        self.assertEqual(bag_status("unavailable", True), BagStatus.UNKNOWN)
        self.assertEqual(bag_status("off", False), BagStatus.NOT_CONFIGURED)
        self.assertIsNone(parse_state("unknown"))


if __name__ == "__main__":
    unittest.main()
