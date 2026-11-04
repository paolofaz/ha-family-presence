"""RC8: persisted, per-source physical event display without FSM feedback."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import types
import unittest

from custom_components.family_presence.access_history import AccessHistory
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import State
from test_source_adapter import FakeHA, ha_event, load_source_module
from test_shadow_sensor import load_sensor_module


CONFIG = {
    "gate_entities": ["switch.cancelletto", "switch.carrabile", "lock.gate_side"],
    "door_contact": "binary_sensor.porta",
    "door_lock": "lock.porta",
}


class AccessHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 4, 14, 40, tzinfo=timezone.utc)
        self.history = AccessHistory(CONFIG)
        self.engine = ShadowCoordinator(
            [PersonSources("paolo", "Paolo")],
            read_state=lambda _id: None, clock=lambda: self.now,
        )
        self.module, _ = load_source_module()
        self.hass = FakeHA()
        self.adapter = self.module.ShadowSourceAdapter(
            self.hass, CONFIG, self.engine, self.history,
        )
        self.adapter.start()

    async def asyncTearDown(self):
        await self.adapter.async_stop()

    async def test_event_types_and_two_distinct_gates(self):
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "switch.carrabile", "off", "on", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "lock.gate_side", "locked", "unlocked", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "binary_sensor.porta", "off", "on", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "binary_sensor.porta", "on", "off", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "lock.porta", "locked", "unlocked", self.now,
        ))
        self.now += timedelta(seconds=15)
        self.adapter._changed(ha_event(
            "lock.porta", "unlocked", "locked", self.now,
        ))
        attrs = self.history.attributes
        self.assertEqual(len(attrs["cancelli"]), 3)
        self.assertNotEqual(
            attrs["cancelli"]["switch.cancelletto"],
            attrs["cancelli"]["switch.carrabile"],
        )
        self.assertIsNotNone(attrs["cancelli"]["lock.gate_side"])
        self.assertNotEqual(attrs["porta_aperta"], attrs["porta_chiusa"])
        self.assertNotEqual(
            attrs["serratura_sbloccata"], attrs["serratura_bloccata"],
        )
        self.assertEqual(self.history.state, "Serratura bloccata")
        self.assertEqual(attrs["ultima_sorgente"], "lock.porta")
        self.assertEqual(attrs["ultimo_evento_alle"], self.now.isoformat())

    async def test_recovery_and_spurious_changes_do_not_generate_events(self):
        count = []
        self.history.async_add_listener(lambda: count.append("event"))
        for old, new in [
            (None, "on"), ("unavailable", "on"), ("unknown", "off"),
            ("off", "unavailable"), ("on", "on"), ("on", "off"),
        ]:
            self.adapter._changed(ha_event(
                "switch.cancelletto", old, new, self.now,
            ))
        self.adapter._changed(ha_event(
            "lock.porta", "unavailable", "locked", self.now,
        ))
        self.assertEqual(count, [])
        self.assertEqual(self.history.state, "Nessun evento")
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        self.assertEqual(count, ["event"])
        # Duplicate callback and older time cannot overwrite the latest value.
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on",
            self.now - timedelta(seconds=5),
        ))
        self.assertEqual(count, ["event"])

    async def test_display_history_restored_but_physical_evidence_is_not(self):
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        snapshot = self.history.snapshot()
        restored = AccessHistory(CONFIG)
        self.assertEqual(restored.restore_snapshot(snapshot), 1)
        self.assertEqual(restored.attributes, self.history.attributes)
        new_engine = ShadowCoordinator(
            [PersonSources("paolo", "Paolo")],
            read_state=lambda _id: None, clock=lambda: self.now,
        )
        self.assertEqual(new_engine._physical, {})
        self.assertFalse(new_engine._recent("gate", self.now, 120))
        self.assertEqual(self.engine._physical["gate"], self.now)

    async def test_stale_or_removed_sources_are_excluded_during_restore(self):
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        self.now += timedelta(seconds=1)
        self.adapter._changed(ha_event(
            "switch.carrabile", "off", "on", self.now,
        ))
        old = self.history.snapshot()
        new_config = {**CONFIG, "gate_entities": ["switch.cancelletto"]}
        restored = AccessHistory(new_config)
        self.assertEqual(restored.restore_snapshot(old), 1)
        self.assertEqual(
            list(restored.attributes["cancelli"]), ["switch.cancelletto"],
        )
        self.assertNotIn("switch.carrabile", str(restored.snapshot()))

    async def test_corrupt_storage_never_produces_physical_events(self):
        malformed = [
            None, "bad", {"format": 999, "events": {}},
            {"format": 1, "events": []},
        ]
        for saved in malformed:
            self.assertEqual(AccessHistory(CONFIG).restore_snapshot(saved), 0)
        bad = {"format": 1, "events": {
            "gate": {"switch.cancelletto": "yesterday",
                     "switch.carrabile": "2026-11-04T15:00:00",
                     "lock.gate_side": 123,
                     "switch.unconfigured": self.now.isoformat()},
        }}
        self.assertEqual(AccessHistory(CONFIG).restore_snapshot(bad), 0)
        self.assertEqual(self.engine.runtime["paolo"].state, None)

    async def test_single_entity_on_casa_receives_only_real_events(self):
        sensor_mod = load_sensor_module()
        sensor = sensor_mod.AccessHistorySensor("entry", self.history)
        self.assertEqual(sensor._attr_unique_id, "entry_last_access_events")
        self.assertEqual(sensor._attr_name, "Ultimi eventi accessi")
        self.assertEqual(sensor._attr_device_info["name"], "Casa")
        self.assertEqual(sensor._attr_entity_category, "diagnostic")
        calls = []
        sensor.async_write_ha_state = lambda: calls.append(True)
        self.assertEqual(sensor.native_value, "Nessun evento")
        sensor._access_updated()
        self.assertEqual(calls, [])
        self.adapter._changed(ha_event(
            "switch.cancelletto", "off", "on", self.now,
        ))
        sensor._access_updated()
        self.assertEqual(len(calls), 1)
        self.assertEqual(sensor.native_value, "Cancello azionato")
        sensor._access_updated()
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            sensor.extra_state_attributes["cancelli"]["switch.cancelletto"],
            self.now.isoformat(),
        )
        # Unrelated FSM updates do not affect this diagnostic sensor.
        await self.engine.force_state("paolo", State.AWAY)
        sensor._access_updated()
        self.assertEqual(len(calls), 1)

    async def test_sensor_platform_adds_only_one_access_entity(self):
        sensor_mod = load_sensor_module()
        entry = types.SimpleNamespace(
            entry_id="entry",
            runtime_data=types.SimpleNamespace(
                engine=self.engine, access_history=self.history,
                profile="final",
            ),
        )
        registered = []
        await sensor_mod.async_setup_entry(None, entry, registered.extend)
        self.assertEqual(len(registered), 3)
        self.assertEqual(
            len([x for x in registered
                 if isinstance(x, sensor_mod.AccessHistorySensor)]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
