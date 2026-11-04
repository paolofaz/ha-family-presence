"""Prove that production entities do not write redundant HA states.

These tests execute the real entity callbacks with HA Entity methods stubbed.
Calls counted below are the calls that would otherwise reach Home Assistant's
state machine and potentially increase Recorder/history churn.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State
from custom_components.family_presence.presentation import FINAL
from test_shadow_sensor import load_sensor_module
from test_alpha8_binary_sensor import load_binary_sensor_module


class RecorderNoiseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 17, 0, tzinfo=timezone.utc)
        self.readings = {
            "bag": "off", "watch": "off",
            "phone": "not_home", "phone2": "not_home",
        }

        async def no_wait(_):
            return None

        self.engine = ShadowCoordinator([
            PersonSources(
                "giulia", "Giulia", iphone="phone", watch="watch", bag="bag",
            ),
            PersonSources("paolo", "Paolo", iphone="phone2"),
        ], read_state=self.readings.get, clock=lambda: self.now, sleep=no_wait)
        self.sensor_module = load_sensor_module()
        self.binary_module = load_binary_sensor_module()

    @staticmethod
    def attach_counter(entity):
        calls = []
        entity.async_write_ha_state = lambda: calls.append(1)
        return calls

    async def test_presence_attributes_are_minimal_and_static_without_events(self):
        person = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "giulia", FINAL
        )
        self.assertEqual(person.native_value, None)
        self.assertEqual(
            set(person.extra_state_attributes),
            {"reason", "last_transition", "bag_return_eligible"},
        )
        self.assertEqual(person.extra_state_attributes["bag_return_eligible"], False)
        self.assertIsNone(person.extra_state_attributes["last_transition"])
        paolo = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "paolo", FINAL
        )
        self.assertEqual(set(paolo.extra_state_attributes),
                         {"reason", "last_transition"})
        self.assertEqual(
            self.binary_module.ShadowAllAwayBinarySensor(
                "entry", self.engine, FINAL
            ).extra_state_attributes, {},
        )

    async def test_ignored_ble_events_do_not_publish_person_or_aggregate(self):
        person = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "giulia", FINAL
        )
        aggregate = self.binary_module.ShadowAllAwayBinarySensor(
            "entry", self.engine, FINAL
        )
        p_writes = self.attach_counter(person)
        a_writes = self.attach_counter(aggregate)
        for i in range(12):
            self.now += timedelta(seconds=1)
            self.engine.note_ignored(
                "giulia", Event.WATCH_LOST, at=self.now,
                reason="Nessuna correlazione fisica",
            )
            self.readings["bag"] = "on" if i % 2 else "off"
            person._shadow_updated("giulia")
            aggregate._updated("giulia")
        self.assertEqual(p_writes, [])
        self.assertEqual(a_writes, [])
        self.assertEqual(self.engine.runtime["giulia"].ignored_count, 12)

    async def test_source_change_without_fsm_transition_is_not_a_state_write(self):
        person = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "giulia", FINAL
        )
        calls = self.attach_counter(person)
        for state in ("on", "off", "unavailable", "on"):
            self.readings["watch"] = state
            self.engine.notify_source_update("giulia")
            person._shadow_updated("giulia")
        self.assertEqual(calls, [])

    async def test_real_presence_transition_publishes_once_and_keeps_reason(self):
        person = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "giulia", FINAL
        )
        calls = self.attach_counter(person)
        self.now += timedelta(seconds=1)
        await self.engine.force_state("giulia", State.HOME)
        person._shadow_updated("giulia")
        self.assertEqual(len(calls), 1)
        person._shadow_updated("giulia")
        self.assertEqual(len(calls), 1)
        attrs = person.extra_state_attributes
        self.assertEqual(attrs["reason"], "Forzato in casa manualmente")
        self.assertIsNotNone(attrs["last_transition"])
        self.assertTrue(attrs["last_transition"].startswith("2026-11-04T17:00:01"))

    async def test_all_away_reported_only_when_boolean_flips(self):
        aggregate = self.binary_module.ShadowAllAwayBinarySensor(
            "entry", self.engine, FINAL
        )
        calls = self.attach_counter(aggregate)
        await self.engine.force_state("giulia", State.AWAY)
        aggregate._updated("giulia")
        self.assertFalse(aggregate.is_on)
        self.assertEqual(calls, [])
        self.now += timedelta(seconds=1)
        await self.engine.force_state("paolo", State.AWAY)
        aggregate._updated("paolo")
        self.assertTrue(aggregate.is_on)
        self.assertEqual(len(calls), 1)
        self.engine.note_ignored("giulia", Event.WATCH_LOST, at=self.now,
                                 reason="BLE ignorato")
        aggregate._updated("giulia")
        self.assertEqual(len(calls), 1)
        self.now += timedelta(seconds=1)
        self.readings["watch"] = "on"
        self.readings["phone"] = "not_home"
        await self.engine.process("giulia", Event.WATCH_SEEN, event_time=self.now)
        aggregate._updated("giulia")
        self.assertFalse(aggregate.is_on)  # NEAR_HOME is not certainly empty.
        self.assertEqual(len(calls), 2)
        aggregate._updated("giulia")
        self.assertEqual(len(calls), 2)

    async def test_household_diagnostic_ignores_repeated_noop_callbacks(self):
        diag = self.sensor_module.ShadowHouseholdSensor(
            "entry", self.engine, FINAL
        )
        writes = self.attach_counter(diag)
        for i in range(6):
            self.now += timedelta(seconds=1)
            self.engine.note_ignored("giulia", Event.BAG_ARRIVED,
                                     at=self.now, reason="Ignorato")
            diag._updated("giulia")
        self.assertEqual(writes, [])
        self.assertEqual(diag.extra_state_attributes, {})
        self.readings["watch"] = "unavailable"
        diag._updated("giulia")
        self.assertEqual(len(writes), 1)
        diag._updated("paolo")
        self.assertEqual(len(writes), 1)
        self.assertIn("source_warnings", diag.extra_state_attributes)

    async def test_bag_authority_change_remains_visible_without_ble_spam(self):
        person = self.sensor_module.ShadowPersonSensor(
            "entry", self.engine, "giulia", FINAL
        )
        calls = self.attach_counter(person)
        self.now += timedelta(seconds=1)
        await self.engine.force_state("giulia", State.HOME)
        person._shadow_updated("giulia")
        before = len(calls)
        self.now += timedelta(seconds=1)
        self.readings["bag"] = "on"
        self.engine.notify_source_update("giulia")
        person._shadow_updated("giulia")
        self.assertEqual(len(calls), before)
        # School window is not active at 17:00 UTC; the bag event is ignored.
        self.readings["bag"] = "off"
        await self.engine.process("giulia", Event.BAG_LEFT, event_time=self.now)
        person._shadow_updated("giulia")
        self.assertEqual(len(calls), before)
        self.assertEqual(person.extra_state_attributes["bag_return_eligible"], False)


if __name__ == "__main__":
    unittest.main()
