"""Security contracts for deliberate backpack exceptions in shadow mode."""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import BagPolicy, Event, State


class ManualBackpackExceptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 11, 0, tzinfo=timezone.utc)
        self.state = {
            "bag": "off", "watch": "on", "iphone": "home", "reference": "away",
        }

        async def instant_sleep(_):
            return None

        self.sleep = instant_sleep

    def coordinator(self, *, policy=BagPolicy.ALWAYS, bag="bag"):
        return ShadowCoordinator(
            [PersonSources(
                "member", "Member", iphone="iphone", watch="watch",
                bag=bag, reference="reference", bag_policy=policy,
            )],
            read_state=self.state.get,
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    async def test_manual_home_needs_deliberate_action_and_absent_bag(self):
        c = self.coordinator()
        await c.reconcile()
        self.assertEqual(c.state("member"), State.AWAY)
        self.assertTrue(c.manual_home_available("member"))
        self.assertTrue(await c.confirm_home_without_bag("member"))
        self.assertFalse(c.manual_home_available("member"))
        self.assertFalse(await c.confirm_home_without_bag("member"))
        self.assertEqual(c.state("member"), State.HOME)
        self.assertEqual(
            c.runtime["member"].last_reason,
            "Presenza in casa confermata manualmente senza zaino",
        )
        self.assertEqual(c.runtime["member"].state_origin, "manual_confirmation")
        self.assertIs(c.all_away(), False)

    async def test_manual_home_refused_for_present_bag_or_school_window_policy(self):
        c = self.coordinator()
        self.state["bag"] = "on"
        self.assertFalse(await c.confirm_home_without_bag("member"))
        self.assertIsNone(c.state("member"))
        self.state["bag"] = "unknown"
        self.assertFalse(await c.confirm_home_without_bag("member"))
        self.state["bag"] = "off"
        legacy = self.coordinator(policy=BagPolicy.LEGACY)
        self.assertFalse(await legacy.confirm_home_without_bag("member"))
        missing = self.coordinator(bag=None)
        self.assertFalse(await missing.confirm_home_without_bag("member"))

    async def test_phone_watch_gate_and_bag_off_cannot_override_confirmed_home(self):
        c = self.coordinator()
        await c.reconcile()
        await c.confirm_home_without_bag("member")
        self.state["iphone"] = "not_home"
        for event in (
            Event.IPHONE_LEFT, Event.WATCH_LOST, Event.PHYSICAL_ENTRY,
            Event.RECONCILE, Event.BAG_LEFT, Event.WATCH_SEEN,
        ):
            with self.subTest(event=event):
                self.assertIsNone(
                    await c.process("member", event, event_time=self.now)
                )
                self.assertEqual(c.state("member"), State.HOME)
                self.assertTrue(c.runtime["member"].manual_home_active)
        self.assertEqual(
            c.runtime["member"].manual_suppressed_event, Event.WATCH_SEEN
        )
        self.assertIs(c.all_away(), False)

    async def test_review_due_never_auto_converts_home_to_away(self):
        c = self.coordinator()
        await c.confirm_home_without_bag("member")
        self.assertFalse(c.manual_review_due("member"))
        expected = self.now + timedelta(hours=8)
        self.assertEqual(c.runtime["member"].manual_home_review_at, expected)
        self.now += timedelta(hours=9)
        self.assertTrue(c.manual_review_due("member"))
        await c.process("member", Event.RECONCILE, event_time=self.now)
        self.assertEqual(c.state("member"), State.HOME)
        self.assertIs(c.all_away(), False)

    async def test_genuine_bag_return_ends_hold_and_keeps_home(self):
        c = self.coordinator()
        await c.confirm_home_without_bag("member")
        self.state["bag"] = "on"
        result = await c.process("member", Event.BAG_ARRIVED, event_time=self.now)
        self.assertEqual(result.current, State.HOME)
        self.assertFalse(c.runtime["member"].manual_home_active)
        self.assertEqual(c.runtime["member"].manual_last_action, "bag_present")
        await c.process("member", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(c.state("member"), State.AWAY)

    async def test_provider_unknown_does_not_release_hold_but_recovered_on_does(self):
        c = self.coordinator()
        await c.confirm_home_without_bag("member")
        self.state["bag"] = "unavailable"
        await c.process("member", Event.RECONCILE, event_time=self.now)
        self.assertTrue(c.runtime["member"].manual_home_active)
        self.assertEqual(c.state("member"), State.HOME)
        self.state["bag"] = "on"
        await c.process("member", Event.RECONCILE, event_time=self.now)
        self.assertFalse(c.runtime["member"].manual_home_active)
        self.assertEqual(c.state("member"), State.HOME)
        self.assertEqual(c.runtime["member"].manual_last_action, "bag_present")

    async def test_revocation_goes_unknown_not_away_and_needs_new_evidence(self):
        c = self.coordinator()
        await c.confirm_home_without_bag("member")
        self.assertTrue(await c.revoke_manual_home("member"))
        self.assertFalse(await c.revoke_manual_home("member"))
        self.assertIsNone(c.state("member"))
        self.assertTrue(c.runtime["member"].post_manual_ambiguity)
        self.assertIsNone(c.all_away())
        for event in (Event.RECONCILE, Event.PHYSICAL_ENTRY, Event.WATCH_LOST):
            await c.process("member", event, event_time=self.now)
            self.assertIsNone(c.state("member"))
            self.assertIsNone(c.all_away())
        # A genuine later iPhone HOME->OUT event is separate departure proof.
        self.state["iphone"] = "not_home"
        await c.process("member", Event.IPHONE_LEFT, event_time=self.now)
        self.assertFalse(c.runtime["member"].post_manual_ambiguity)
        self.assertEqual(c.state("member"), State.AWAY)
        self.assertIs(c.all_away(), True)

    async def test_revocation_ambiguity_persists_through_restart(self):
        first = self.coordinator()
        await first.confirm_home_without_bag("member")
        await first.revoke_manual_home("member")
        saved = first.snapshot()
        self.assertEqual(saved["format"], 3)
        self.assertIsNone(saved["people"]["member"]["state"])
        second = self.coordinator()
        self.assertEqual(second.restore_snapshot(saved), 1)
        self.assertIsNone(second.state("member"))
        self.assertTrue(second.runtime["member"].post_manual_ambiguity)
        await second.reconcile()
        self.assertIsNone(second.state("member"))
        self.assertIsNone(second.all_away())

    async def test_active_manual_home_survives_restart_without_automatic_away(self):
        first = self.coordinator()
        await first.confirm_home_without_bag("member")
        saved = first.snapshot()
        second = self.coordinator()
        self.assertEqual(second.restore_snapshot(saved), 1)
        self.assertTrue(second.runtime["member"].manual_home_active)
        self.assertEqual(second.state("member"), State.HOME)
        self.assertIsNone(second.all_away())  # Restored quality is unverified.
        await second.reconcile()
        self.assertEqual(second.state("member"), State.HOME)
        self.assertIsNone(second.all_away())
        self.assertTrue(second.runtime["member"].manual_home_active)

    async def test_format_two_snapshots_still_restore_without_manual_hold(self):
        first = self.coordinator()
        await first.reconcile()
        record = first.snapshot()
        record["format"] = 2
        del record["people"]["member"]["manual_home"]
        second = self.coordinator()
        self.assertEqual(second.restore_snapshot(record), 1)
        self.assertEqual(second.state("member"), State.AWAY)
        self.assertFalse(second.runtime["member"].manual_home_active)

    async def test_corrupt_manual_data_never_activates_hold(self):
        first = self.coordinator()
        await first.confirm_home_without_bag("member")
        data = first.snapshot()
        data["people"]["member"]["manual_home"]["since"] = "not-a-time"
        second = self.coordinator()
        second.restore_snapshot(data)
        self.assertFalse(second.runtime["member"].manual_home_active)
        self.assertEqual(second.state("member"), State.HOME)
        self.assertIsNone(second.all_away())

    async def test_manual_action_invalidates_queued_watch_on_hypothesis(self):
        started = asyncio.Event()
        released = asyncio.Event()

        async def held(_):
            started.set()
            await released.wait()

        c = self.coordinator()
        self.state["watch"] = "on"
        c._sleep = held
        revision = c.note_person_event("member")
        task = asyncio.create_task(c.process(
            "member", Event.WATCH_SEEN,
            event_time=self.now, revision=revision,
        ))
        await started.wait()
        # The per-person lock serializes a human action with pending Watch ON.
        # Release the pending hypothesis first, then confirm HOME explicitly.
        released.set()
        await task
        before = c.runtime["member"].source_revision
        self.assertTrue(await c.confirm_home_without_bag("member"))
        self.assertGreater(c.runtime["member"].source_revision, before)
        self.assertEqual(c.state("member"), State.HOME)


if __name__ == "__main__":
    unittest.main()
