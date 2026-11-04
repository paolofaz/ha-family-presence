"""Regression contract: a bag can only resolve its own documented trip.

The guard prevents a delayed BLE bag reconnect from falsely disarming the
external YAML alarm after an iPhone, Watch or manual AWAY. No HA installation
is needed for these coordinator-level tests.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.family_presence.bag_schedule import BagSchedule, ALL_DAYS
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State


class BagReturnCausalityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
        self.inputs = {"bag": "on", "iphone": "home", "watch": "off"}

        async def instant_sleep(_):
            return None

        self.sleep = instant_sleep

    def engine(self, *, schedule=None):
        if schedule is None:
            schedule = BagSchedule(True, "00:00", "00:00", ALL_DAYS)
        return ShadowCoordinator(
            [PersonSources(
                "kid", "Kid", iphone="iphone", watch="watch", bag="bag",
                bag_schedule=schedule,
            )],
            read_state=self.inputs.get,
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    async def bag_left(self, engine):
        self.now += timedelta(seconds=2)
        self.inputs["bag"] = "off"
        return await engine.process("kid", Event.BAG_LEFT, event_time=self.now)

    async def bag_arrived(self, engine):
        self.now += timedelta(seconds=2)
        self.inputs["bag"] = "on"
        return await engine.process("kid", Event.BAG_ARRIVED, event_time=self.now)

    async def test_bag_round_trip_from_home_and_only_once(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        self.assertEqual((await self.bag_left(c)).current, State.AWAY)
        self.assertEqual(c.runtime["kid"].last_reason, "Bag left")
        self.assertTrue(c.runtime["kid"].bag_return_eligible)
        self.assertEqual((await self.bag_arrived(c)).current, State.HOME)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await c.process(
            "kid", Event.BAG_ARRIVED, event_time=self.now,
        ))
        self.assertEqual(c.runtime["kid"].last_ignored_event, Event.BAG_ARRIVED)
        self.assertEqual(c.state("kid"), State.HOME)

    async def test_phone_away_cannot_be_reset_by_bag_reconnect(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        self.inputs["iphone"] = "not_home"
        self.now += timedelta(seconds=1)
        await c.process("kid", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(c.state("kid"), State.AWAY)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIn("non risulta una uscita", c.runtime["kid"].last_ignored_reason)

    async def test_bag_departure_cannot_steal_existing_iphone_away(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        self.inputs["iphone"] = "not_home"
        self.now += timedelta(seconds=1)
        await c.process("kid", Event.IPHONE_LEFT, event_time=self.now)
        self.assertIsNone(await self.bag_left(c))
        self.assertEqual(c.runtime["kid"].last_reason, "iPhone left home zone")
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)

    async def test_manual_away_is_not_overridden_by_bag_arrival(self):
        c = self.engine()
        await c.force_state("kid", State.AWAY)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)
        self.now += timedelta(seconds=1)
        self.inputs["iphone"] = "home"
        self.assertEqual((await c.process(
            "kid", Event.IPHONE_ARRIVED, event_time=self.now,
        )).current, State.HOME)

    async def test_manual_away_revokes_previous_bag_trip(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        await self.bag_left(c)
        self.assertTrue(c.runtime["kid"].bag_return_eligible)
        self.now += timedelta(seconds=1)
        await c.force_state("kid", State.AWAY)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)

    async def test_near_home_keeps_bag_origin_until_its_arrival(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        await self.bag_left(c)
        self.now += timedelta(seconds=3)
        self.inputs["watch"] = "on"
        decision = await c.process("kid", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(decision.current, State.NEAR_HOME)
        self.assertTrue(c.runtime["kid"].bag_return_eligible)
        self.assertEqual((await self.bag_arrived(c)).current, State.HOME)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)

    async def test_near_home_from_iphone_away_does_not_grant_bag_right(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        self.inputs["iphone"] = "not_home"
        self.now += timedelta(seconds=1)
        await c.process("kid", Event.IPHONE_LEFT, event_time=self.now)
        self.now += timedelta(seconds=3)
        self.inputs["watch"] = "on"
        self.assertEqual((await c.process(
            "kid", Event.WATCH_SEEN, event_time=self.now,
        )).current, State.NEAR_HOME)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.NEAR_HOME)

    async def test_watch_lost_from_near_home_revokes_bag_trip(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        await self.bag_left(c)
        self.now += timedelta(seconds=3)
        self.inputs["watch"] = "on"
        await c.process("kid", Event.WATCH_SEEN, event_time=self.now)
        self.now += timedelta(seconds=3)
        self.inputs["watch"] = "off"
        self.assertEqual((await c.process(
            "kid", Event.WATCH_LOST, event_time=self.now,
        )).current, State.AWAY)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)

    async def test_phone_departure_replaces_bag_reason_even_if_already_away(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        await self.bag_left(c)
        changed_at = c.runtime["kid"].last_changed
        self.now += timedelta(seconds=3)
        self.inputs["iphone"] = "not_home"
        event = await c.process("kid", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(event.current, State.AWAY)
        self.assertEqual(c.runtime["kid"].last_reason, "iPhone left home zone")
        self.assertEqual(c.runtime["kid"].last_changed, changed_at)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)

    async def test_watch_confirmed_away_does_not_grant_bag_return(self):
        c = self.engine()
        c.runtime["kid"].state = State.HOME
        self.now += timedelta(seconds=1)
        c.record_physical("gate", self.now - timedelta(seconds=5))
        await c.process(
            "kid", Event.WATCH_LOST, event_time=self.now,
            last_seen_before_off=self.now,
        )
        self.assertEqual(c.state("kid"), State.AWAY)
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(c))
        self.assertEqual(c.state("kid"), State.AWAY)

    async def test_restart_keeps_bag_origin_only_from_new_snapshot_flag(self):
        first = self.engine()
        first.runtime["kid"].state = State.HOME
        await self.bag_left(first)
        snapshot = first.snapshot()
        self.assertEqual(snapshot["format"], 5)
        self.assertIs(snapshot["people"]["kid"]["bag_return_eligible"], True)
        restored = self.engine()
        self.assertEqual(restored.restore_snapshot(snapshot), 1)
        self.assertEqual(restored.state("kid"), State.AWAY)
        self.assertTrue(restored.runtime["kid"].bag_return_eligible)
        self.assertEqual((await self.bag_arrived(restored)).current, State.HOME)

    async def test_disabled_schedule_revokes_restored_bag_authority(self):
        first = self.engine()
        first.runtime["kid"].state = State.HOME
        await self.bag_left(first)
        snapshot = first.snapshot()
        disabled = self.engine(schedule=BagSchedule(
            False, "00:00", "00:00", ALL_DAYS,
        ))
        self.assertEqual(disabled.restore_snapshot(snapshot), 1)
        self.assertFalse(disabled.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(disabled))
        self.assertEqual(disabled.state("kid"), State.AWAY)

    async def test_pre_rc6_snapshot_fails_closed_even_if_reason_claims_bag(self):
        initial = self.engine()
        initial.runtime["kid"].state = State.HOME
        await self.bag_left(initial)
        snapshot = initial.snapshot()
        del snapshot["people"]["kid"]["bag_return_eligible"]
        restored = self.engine()
        self.assertEqual(restored.restore_snapshot(snapshot), 1)
        self.assertEqual(restored.runtime["kid"].last_reason, "Bag left")
        self.assertFalse(restored.runtime["kid"].bag_return_eligible)
        self.assertIsNone(await self.bag_arrived(restored))
        self.assertEqual(restored.state("kid"), State.AWAY)

    async def test_corrupt_snapshot_provenance_cannot_authorize_arrival(self):
        original = self.engine()
        original.runtime["kid"].state = State.HOME
        await self.bag_left(original)
        for value in ("true", 1, [], None):
            snapshot = original.snapshot()
            snapshot["people"]["kid"]["bag_return_eligible"] = value
            restarted = self.engine()
            self.assertEqual(restarted.restore_snapshot(snapshot), 1)
            self.assertFalse(restarted.runtime["kid"].bag_return_eligible)
        for state in ("home", "unknown"):
            snapshot = original.snapshot()
            snapshot["people"]["kid"]["state"] = state
            restarted = self.engine()
            restored = restarted.restore_snapshot(snapshot)
            if state == "home":
                self.assertEqual(restored, 1)
                self.assertFalse(restarted.runtime["kid"].bag_return_eligible)
            else:
                self.assertEqual(restored, 0)

    async def test_departure_out_of_window_never_grants_return(self):
        disabled = BagSchedule(True, "07:00", "07:10", ALL_DAYS)
        c = self.engine(schedule=disabled)
        c.runtime["kid"].state = State.HOME
        self.assertIsNone(await self.bag_left(c))
        self.assertFalse(c.runtime["kid"].bag_return_eligible)
        self.assertEqual(c.state("kid"), State.HOME)
        self.assertIsNone(await self.bag_arrived(c))

    async def test_phone_and_watch_can_still_confirm_home_while_bag_absent(self):
        c = self.engine()
        c.runtime["kid"].state = State.AWAY
        self.inputs["bag"] = "off"
        self.now += timedelta(seconds=1)
        self.assertEqual((await c.process(
            "kid", Event.IPHONE_ARRIVED, event_time=self.now,
        )).current, State.HOME)
        self.now += timedelta(seconds=1)
        c.runtime["kid"].state = State.AWAY
        c.record_physical("gate", self.now)
        self.inputs["watch"] = "on"
        self.assertEqual((await c.process(
            "kid", Event.WATCH_SEEN, event_time=self.now,
        )).current, State.HOME)


if __name__ == "__main__":
    unittest.main()
