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

    async def test_subscribes_reference_and_all_mapped_sensors(self):
        entities, _callback = self.events.callbacks[-1]
        self.assertEqual(set(entities),
                         {"phone", "bag", "watch", "ref", "switch.gate",
                          "binary_sensor.door", "lock.front"})

    async def test_unavailable_to_off_bag_only_reconciles_not_arrives(self):
        self.engine.runtime["child"].state = State.HOME
        self.inputs["bag"] = "off"
        self.adapter._changed(ha_event("bag", "unavailable", "off", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        self.assertEqual(self.engine.runtime["child"].last_reason, "Bag absent (priority)")
        # Returning from unavailable to ON is not a physical OFF->ON bag arrival.
        self.inputs["bag"] = "on"
        self.adapter._changed(ha_event("bag", "unavailable", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)

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

    async def test_neighbor_gate_vetoed_by_absent_bag(self):
        self.inputs["bag"] = "off"
        self.adapter._changed(ha_event("switch.gate", "off", "on", self.now))
        await self.drain()
        self.adapter._changed(ha_event("watch", "off", "on", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)

    async def test_reference_update_refreshes_diagnostics_not_fsm(self):
        notifications = []
        self.engine.async_add_listener(notifications.append)
        self.inputs["ref"] = "home"
        self.adapter._changed(ha_event("ref", "away", "home", self.now))
        await self.drain()
        self.assertEqual(self.engine.state("child"), State.AWAY)
        self.assertIn("child", notifications)

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
