"""Stable v1.0 regression tests for safety, persistence and diagnostics.

All tests run without installing Home Assistant, alongside the existing
production FSM suite. No test calls alarm, lock, or gate actuators.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from custom_components.family_presence.access_history import AccessHistory
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator, Windows
from custom_components.family_presence.diagnostic_data import build_diagnostics
from custom_components.family_presence.diagnostics import async_get_config_entry_diagnostics
from custom_components.family_presence.fsm import Event, State
from custom_components.family_presence.presentation import FINAL
from test_shadow_sensor import load_sensor_module


class V1CorrelationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
        self.readings = {"watch": "on", "iphone": "not_home"}

        async def no_delay(_):
            return None

        self.no_delay = no_delay

    def engine(self, *, seconds=180):
        return ShadowCoordinator(
            [PersonSources("person", "Name", watch="watch", iphone="iphone")],
            read_state=self.readings.get,
            sleep=self.no_delay,
            clock=lambda: self.now,
            windows=Windows(near_home_entry_seconds=seconds),
        )

    async def near_home(self, c):
        await c.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.now += timedelta(seconds=1)
        decision = await c.process("person", Event.WATCH_SEEN, event_time=self.now)
        self.assertEqual(decision.current, State.NEAR_HOME)
        self.assertEqual(c.runtime["person"].near_home_entered_at, self.now)

    async def test_relevant_physical_event_confirms_fresh_near_home(self):
        c = self.engine()
        await self.near_home(c)
        self.now += timedelta(seconds=179)
        c.record_physical("door_open", self.now)
        d = await c.process("person", Event.PHYSICAL_ENTRY,
                            event_time=self.now, physical_kind="door_open")
        self.assertEqual(d.current, State.HOME)

    async def test_stale_shared_door_does_not_confirm_home(self):
        c = self.engine()
        await self.near_home(c)
        self.now += timedelta(seconds=181)
        c.record_physical("door_open", self.now)
        self.assertIsNone(await c.process(
            "person", Event.PHYSICAL_ENTRY,
            event_time=self.now, physical_kind="door_open",
        ))
        self.assertEqual(c.state("person"), State.NEAR_HOME)
        self.assertIn("rilevamento Watch recente",
                      c.runtime["person"].last_ignored_reason)

    async def test_older_physical_event_cannot_confirm_a_later_watch(self):
        c = self.engine()
        await self.near_home(c)
        self.now -= timedelta(seconds=2)
        c.record_physical("gate", self.now)
        self.assertIsNone(await c.process(
            "person", Event.PHYSICAL_ENTRY,
            event_time=self.now, physical_kind="gate",
        ))
        self.assertEqual(c.state("person"), State.NEAR_HOME)

    async def test_configurable_window_changes_only_near_home_confirmation(self):
        c = self.engine(seconds=300)
        await self.near_home(c)
        self.now += timedelta(seconds=250)
        c.record_physical("unlock", self.now)
        d = await c.process("person", Event.PHYSICAL_ENTRY,
                            event_time=self.now, physical_kind="unlock")
        self.assertEqual(d.current, State.HOME)

    async def test_restored_near_home_requires_new_personal_evidence(self):
        c = self.engine()
        await self.near_home(c)
        snapshot = c.snapshot()
        restored = self.engine()
        self.assertEqual(restored.restore_snapshot(snapshot), 1)
        self.assertEqual(restored.state("person"), State.NEAR_HOME)
        self.assertIsNone(restored.runtime["person"].near_home_entered_at)
        self.assertEqual(restored._physical, {})
        self.now += timedelta(seconds=5)
        restored.record_physical("door_open", self.now)
        self.assertIsNone(await restored.process(
            "person", Event.PHYSICAL_ENTRY,
            event_time=self.now, physical_kind="door_open",
        ))
        self.assertEqual(restored.state("person"), State.NEAR_HOME)
        # A fresh independent iPhone arrival always remains authoritative.
        self.now += timedelta(seconds=1)
        self.readings["iphone"] = "home"
        result = await restored.process(
            "person", Event.IPHONE_ARRIVED, event_time=self.now,
        )
        self.assertEqual(result.current, State.HOME)


class V1PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 16, 0, tzinfo=timezone.utc)
        self.sources = {"iphone": "not_home"}

        async def no_delay(_):
            return None

        self.engine = ShadowCoordinator(
            [PersonSources("person", "Member", iphone="iphone")],
            read_state=self.sources.get, clock=lambda: self.now,
            sleep=no_delay,
        )

    async def test_only_accepted_fsm_decisions_schedule_storage(self):
        persisted, ui = [], []
        unsubscribe = self.engine.async_add_persist_listener(lambda: persisted.append(1))
        self.engine.async_add_listener(ui.append)
        self.engine.notify_source_update("person")
        self.engine.note_ignored(
            "person", Event.WATCH_LOST, at=self.now, reason="ignored"
        )
        self.assertEqual(len(ui), 2)
        self.assertEqual(len(persisted), 0)
        self.now += timedelta(seconds=1)
        result = await self.engine.process(
            "person", Event.IPHONE_LEFT, event_time=self.now,
        )
        self.assertEqual(result.current, State.AWAY)
        self.assertEqual(len(persisted), 1)
        self.assertIsNone(await self.engine.process(
            "person", Event.RECONCILE, event_time=self.now,
        ))
        self.assertEqual(len(persisted), 1)
        self.now += timedelta(seconds=1)
        await self.engine.force_state("person", State.HOME)
        self.assertEqual(len(persisted), 2)
        unsubscribe()
        self.now += timedelta(seconds=1)
        await self.engine.force_state("person", State.AWAY)
        self.assertEqual(len(persisted), 2)

    async def test_restored_unverified_is_diagnostic_only(self):
        await self.engine.process("person", Event.IPHONE_LEFT, event_time=self.now)
        snapshot = self.engine.snapshot()
        other = ShadowCoordinator(
            [PersonSources("person", "Member", iphone="iphone")],
            read_state=self.sources.get, clock=lambda: self.now,
        )
        self.assertEqual(other.restore_snapshot(snapshot), 1)
        module = load_sensor_module()
        diagnostic = module.ShadowHouseholdSensor("entry", other, FINAL)
        presence = module.ShadowPersonSensor("entry", other, "person", FINAL)
        self.assertEqual(other.state("person"), State.AWAY)
        self.assertEqual(diagnostic.extra_state_attributes["restored_unverified_members"],
                         ["Member"])
        self.assertNotIn("restored_unverified_members", presence.extra_state_attributes)
        self.now += timedelta(seconds=1)
        await other.process("person", Event.IPHONE_LEFT, event_time=self.now)
        self.assertNotIn("restored_unverified_members",
                         diagnostic.extra_state_attributes)


class V1DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 20, 0, tzinfo=timezone.utc)
        self.states = {
            "device_tracker.iphone_paolo": "Work-Paolo",
            "binary_sensor.watch_paolo": "on",
            "binary_sensor.zaino_paolo": "off",
        }
        self.engine = ShadowCoordinator(
            [PersonSources(
                "paolo_secret_id", "Paolo Segreto",
                iphone="device_tracker.iphone_paolo",
                watch="binary_sensor.watch_paolo",
                bag="binary_sensor.zaino_paolo",
            )],
            read_state=self.states.get,
            clock=lambda: self.now,
        )
        self.history = AccessHistory({
            "gate_entities": ["switch.cancello_privato"],
            "door_contact": "binary_sensor.porta_privata",
            "door_lock": "lock.serratura_privata",
        })
        self.history.record("gate", "switch.cancello_privato", self.now)

    async def test_download_does_not_expose_identifying_inputs_or_zone_names(self):
        await self.engine.process("paolo_secret_id", Event.IPHONE_LEFT,
                                  event_time=self.now)
        report = build_diagnostics(self.engine, self.history)
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        for secret in (
            "Paolo Segreto", "paolo_secret_id",
            "device_tracker.iphone_paolo", "binary_sensor.watch_paolo",
            "binary_sensor.zaino_paolo", "Work-Paolo",
            "switch.cancello_privato", "binary_sensor.porta_privata",
            "lock.serratura_privata",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(report["household"]["configured_members"], 1)
        self.assertEqual(report["members"][0]["id"], "persona_1")
        self.assertEqual(report["members"][0]["sources"]["iphone"], "outside_home")
        self.assertEqual(report["access_history"]["gate"]["observed_sources"], 1)
        self.assertEqual(len(report["members"][0]["recent_events"]), 1)

    async def test_ha_diagnostics_entry_point_returns_the_same_report(self):
        entry = SimpleNamespace(runtime_data=SimpleNamespace(
            engine=self.engine, access_history=self.history,
        ))
        report = await async_get_config_entry_diagnostics(None, entry)
        self.assertEqual(report, build_diagnostics(self.engine, self.history))
        self.assertEqual(report["version"], "1.0.2")


if __name__ == "__main__":
    unittest.main()
