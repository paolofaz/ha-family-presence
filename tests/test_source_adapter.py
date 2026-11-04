"""Contract tests for HA source adapter using lightweight HA API stubs."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import BagPolicy, Event, State
from custom_components.family_presence.bag_schedule import BagSchedule, ALL_DAYS


def load_source_module():
    """Import the actual adapter with only the HA APIs replaced."""
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.Event = object
    core.callback = lambda func: func
    helpers = types.ModuleType("homeassistant.helpers")
    events = types.ModuleType("homeassistant.helpers.event")
    events.callbacks = []
    events.unsubscribed = []

    def subscribe(hass, entities, callback):
        events.callbacks.append((entities, callback))
        def unsubscribe():
            events.unsubscribed.append(True)
        return unsubscribe

    events.async_track_state_change_event = subscribe
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.parse_datetime = datetime.fromisoformat
    modules = {
        "homeassistant": ha,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.event": events,
        "homeassistant.util": util,
        "homeassistant.util.dt": dt,
    }
    src = Path(__file__).resolve().parents[1] / "custom_components" / "family_presence" / "sources.py"
    name = "custom_components.family_presence.sources"
    with patch.dict(sys.modules, modules):
        module = types.ModuleType(name)
        module.__package__ = "custom_components.family_presence"
        spec = importlib.util.spec_from_file_location(name, src)
        module.__spec__ = spec
        spec.loader.exec_module(module)
    return module, events


class FakeHA:
    def __init__(self):
        self.tasks = []

    def async_create_task(self, coro, *, name):
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        return task


def state(value, *, attributes=None):
    return types.SimpleNamespace(state=value, attributes=attributes or {})


def ha_event(entity, old, new, time, *, attrs=None):
    return types.SimpleNamespace(
        time_fired=time,
        data={
            "entity_id": entity,
            "old_state": state(old) if old is not None else None,
            "new_state": state(new, attributes=attrs) if new is not None else None,
        },
    )


class SourceAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mod, self.events = load_source_module()
        self.now = datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc)
        self.inputs = {"bag": "on", "watch": "on", "phone": "not_home", "ref": "away"}
        self.hass = FakeHA()

        async def immediate_sleep(_):
            return None

        self.engine = ShadowCoordinator(
            [PersonSources("child", "Child", iphone="phone", watch="watch",
                           bag="bag", reference="ref", bag_policy=BagPolicy.ALWAYS)],
            read_state=self.inputs.get,
            sleep=immediate_sleep,
            clock=lambda: self.now,
        )
        # Explicit fixture setup; the live coordinator never seeds from YAML.
        self.engine.runtime["child"].state = State.AWAY
        self.engine.runtime["child"].state_origin = "test_fixture"
        self.adapter = self.mod.ShadowSourceAdapter(
            self.hass,
            {"gate_entities": ["switch.gate"], "door_contact": "binary_sensor.door",
             "door_lock": "lock.front"},
            self.engine,
        )
        self.adapter.start()

    async def asyncTearDown(self):
        await self.adapter.async_stop()

    async def drain(self):
        # FakeHA tasks are real asyncio tasks scheduled by the adapter.
        await asyncio.gather(*self.hass.tasks, return_exceptions=False)
        self.hass.tasks.clear()

    async def test_stable_person_identifier_is_independent_of_display_name(self):
        config = {"people": [
            {"person_name": "Member", "person_id": "stable-id-42",
             "iphone_tracker": "phone", "watch_sensor": "watch",
             "bag_sensor": "bag", "bag_policy": "always"}
        ]}
        first = self.mod._person_specs(config)
        config["people"][0]["person_name"] = "New display name"
        second = self.mod._person_specs(config)
        self.assertEqual(first[0].key, "stable-id-42")
        self.assertEqual(second[0].key, "stable-id-42")
        self.assertNotEqual(first[0].name, second[0].name)

    async def test_legacy_config_without_id_remains_compatible(self):
        legacy = {"people": [{"person_name": "Child", "bag_sensor": "bag"}]}
        self.assertEqual(self.mod._person_specs(legacy)[0].key, "child")

    async def test_bag_policy_options_override_initial_policy(self):
        config = {"people": [
            {"person_name": "Child", "person_id": "child-id",
             "bag_sensor": "bag", "bag_policy": "always"}
        ]}
        defaults = self.mod._person_specs(config)
        overrides = self.mod._person_specs(config, {
            "bag_policies": {"child-id": "legacy"},
        })
        self.assertEqual(defaults[0].bag_policy, BagPolicy.ALWAYS)
        self.assertEqual(overrides[0].bag_policy, BagPolicy.LEGACY)
        self.assertEqual(config["people"][0]["bag_policy"], "always")

    async def test_bag_policy_options_for_other_person_do_not_leak(self):
        config = {"people": [
            {"person_name": "Child", "person_id": "child-id", "bag_sensor": "bag"},
            {"person_name": "Other", "person_id": "other-id", "bag_sensor": "bag2"},
        ]}
        specs = self.mod._person_specs(config, {"bag_policies": {
            "child-id": "legacy",
        }})
        self.assertEqual([p.bag_policy for p in specs],
                         [BagPolicy.LEGACY, BagPolicy.LEGACY])

    async def test_legacy_name_based_policy_option_is_supported(self):
        config = {"people": [{"person_name": "Member", "bag_sensor": "bag"}]}
        specs = self.mod._person_specs(config, {
            "bag_policies": {"member": "legacy"},
        })
        self.assertEqual(specs[0].bag_policy, BagPolicy.LEGACY)

    async def test_subscribes_reference_and_all_mapped_sensors(self):
        entities, _callback = self.events.callbacks[-1]
        self.assertEqual(set(entities),
                         {"phone", "bag", "watch", "ref", "switch.gate",
                          "binary_sensor.door", "lock.front"})

    async def test_unavailable_bag_recovery_never_synthesizes_departure_or_arrival(self):
        self.engine.runtime["child"].state = State.HOME
        self.inputs["bag"] = "off"
        self.adapter._changed(ha_event("bag", "unavailable", "off", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.HOME)
        self.inputs["bag"] = "on"
        self.adapter._changed(ha_event("bag", "unavailable", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.HOME)

    async def test_real_bag_transitions_respect_schedule(self):
        self.engine.runtime["child"].state = State.HOME
        self.inputs["bag"] = "off"
        self.adapter._changed(ha_event("bag", "on", "off", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        self.inputs["bag"] = "on"
        self.adapter._changed(ha_event("bag", "off", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.HOME)

    async def test_new_schedule_options_override_migrated_policy_per_person(self):
        config = {"people": [
            {"person_name": "Child", "person_id": "child-id",
             "bag_sensor": "bag", "bag_policy": "always"}
        ]}
        options = {"bag_schedules": {
            "child-id": {"enabled": False, "start": "00:00",
                         "end": "00:00", "days": list(ALL_DAYS)}
        }}
        spec = self.mod._person_specs(config, options)[0]
        self.assertFalse(spec.bag_schedule.enabled)
        self.assertEqual(spec.bag_schedule.start, "00:00")
        self.assertTrue(self.mod._person_specs(config)[0].bag_schedule.includes(self.now))

    async def test_unavailable_watch_on_does_not_create_false_arrival(self):
        self.adapter._changed(ha_event("watch", "unknown", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        self.adapter._changed(ha_event("watch", "off", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.NEAR_HOME)

    async def test_watch_off_exit_uses_last_seen_attribute(self):
        self.inputs.update({"bag": "on", "watch": "off", "phone": "home", "ref": "home"})
        engine = self.engine
        engine.runtime["child"].state = State.HOME
        # Gate 3 mins before Watch OFF trigger, but only 60s before BLE last-seen.
        gate_time = self.now - timedelta(minutes=3)
        self.adapter._changed(ha_event("switch.gate", "off", "on", gate_time))
        await self.drain()
        self.adapter._changed(ha_event(
            "watch", "on", "off", self.now,
            attrs={"last_seen_before_off": (self.now - timedelta(minutes=2)).isoformat()},
        ))
        await self.drain()
        self.assertEqual(engine.state("child"), State.AWAY)

    async def test_gate_and_watch_can_override_prior_bag_absence(self):
        self.inputs["bag"] = "off"
        self.adapter._changed(ha_event("switch.gate", "off", "on", self.now))
        await self.drain()
        self.adapter._changed(ha_event("watch", "off", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.HOME)

    async def test_reference_update_refreshes_diagnostics_not_fsm(self):
        notifications = []
        self.engine.async_add_listener(notifications.append)
        self.engine.notify_source_update("child")
        self.assertEqual(self.engine.parity_status, "aligned")
        self.inputs["ref"] = "home"
        self.adapter._changed(ha_event("ref", "away", "home", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        self.assertEqual(self.engine.parity_status, "aggregate_divergence")
        self.assertIsNotNone(self.engine.parity_diverged_since)
        self.assertIn("child", notifications)

    async def test_direct_legacy_binary_change_updates_only_diagnostics(self):
        await self.adapter.async_stop()
        self.inputs["old_casa_vuota"] = "off"
        self.engine.legacy_aggregate = "old_casa_vuota"
        self.adapter = self.mod.ShadowSourceAdapter(
            self.hass,
            {"gate_entities": [], "door_contact": None, "door_lock": None},
            self.engine,
        )
        self.adapter.start()
        entities, _ = self.events.callbacks[-1]
        self.assertIn("old_casa_vuota", entities)
        old_state = self.engine.state("child")
        observed = []
        self.engine.async_add_listener(observed.append)

        self.inputs["old_casa_vuota"] = "on"
        self.adapter._changed(ha_event(
            "old_casa_vuota", "off", "on", self.now,
        ))
        await self.drain()
        self.assertEqual(self.engine.state("child"), old_state)
        self.assertIs(self.engine.legacy_comparison().actual_legacy_all_away, True)
        self.assertIs(self.engine.legacy_comparison().actual_legacy_matches_shadow, True)
        self.assertIn("child", observed)

    async def test_bag_recovery_is_diagnostic_but_not_a_physical_arrival(self):
        self.inputs["bag"] = "on"
        self.adapter._changed(ha_event("bag", "unknown", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        rt = self.engine.runtime["child"]
        self.assertEqual(rt.last_ignored_event, Event.RECONCILE)
        self.assertIn("Ripristino sensore zaino", rt.last_ignored_reason)

    async def test_invalid_or_attribute_only_changes_do_not_change_fsm(self):
        self.inputs["watch"] = "unavailable"
        self.adapter._changed(ha_event("watch", "on", "unavailable", self.now))
        self.adapter._changed(ha_event("watch", "on", "on", self.now,
                                        attrs={"rssi": -50}))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)

    async def test_unload_unsubscribes_and_drops_tasks(self):
        await self.adapter.async_stop()
        self.assertTrue(self.events.unsubscribed)
        self.assertFalse(self.adapter._tasks)


if __name__ == "__main__":
    unittest.main()
