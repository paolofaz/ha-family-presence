"""Mock Home Assistant button platform for shadow-only manual exceptions."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import BagPolicy, State


def load_buttons():
    root = Path(__file__).resolve().parents[1]
    path = root / "custom_components" / "family_presence" / "button.py"

    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    buttons = types.ModuleType("homeassistant.components.button")

    class ButtonEntity:
        async def async_added_to_hass(self):
            return None

        def async_on_remove(self, cb):
            self._unsubscribe = cb

        def async_write_ha_state(self):
            self._wrote_state = True

    buttons.ButtonEntity = ButtonEntity
    const = types.ModuleType("homeassistant.const")
    const.EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda f: f
    helpers = types.ModuleType("homeassistant.helpers")
    platform = types.ModuleType("homeassistant.helpers.entity_platform")
    platform.AddConfigEntryEntitiesCallback = object

    mocks = {
        "homeassistant": ha, "homeassistant.components": components,
        "homeassistant.components.button": buttons, "homeassistant.const": const,
        "homeassistant.core": core, "homeassistant.helpers": helpers,
        "homeassistant.helpers.entity_platform": platform,
    }
    name = "custom_components.family_presence.button"
    with patch.dict(sys.modules, mocks):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


class FakeStore:
    def __init__(self):
        self.saved = []

    async def async_save(self, snapshot):
        self.saved.append(snapshot)


class ManualButtonsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_buttons()
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        self.data = {"bag": "off"}

        async def no_wait(_):
            pass

        self.engine = ShadowCoordinator(
            [
                PersonSources("kid", "Child", bag="bag"),
                PersonSources("adult", "Adult", iphone="phone"),
                PersonSources("legacy", "Legacy", bag="other_bag",
                              bag_policy=BagPolicy.LEGACY),
            ],
            read_state=self.data.get,
            clock=lambda: self.now,
            sleep=no_wait,
        )
        self.store = FakeStore()
        self.runtime = types.SimpleNamespace(engine=self.engine, store=self.store)
        self.entry = types.SimpleNamespace(entry_id="entry", runtime_data=self.runtime)
        self.entities = []
        await self.module.async_setup_entry(
            types.SimpleNamespace(), self.entry,
            lambda items: self.entities.extend(items),
        )

    async def test_all_members_receive_force_home_and_away(self):
        self.assertEqual(len(self.entities), 6)
        self.assertEqual(
            {(e.person, e.target) for e in self.entities},
            {(person, state) for person in ("kid", "adult", "legacy")
             for state in (State.HOME, State.AWAY)},
        )
        self.assertTrue(all(e._attr_entity_category == "diagnostic" for e in self.entities))

    async def test_force_actions_persist_immediately(self):
        home = next(e for e in self.entities
                    if e.person == "kid" and e.target == State.HOME)
        away = next(e for e in self.entities
                    if e.person == "kid" and e.target == State.AWAY)
        self.assertIn("Forza a casa", home._attr_name)
        self.assertIn("Forza fuori casa", away._attr_name)
        await home.async_press()
        self.assertEqual(self.engine.state("kid"), State.HOME)
        self.assertEqual(len(self.store.saved), 1)
        self.assertEqual(
            self.store.saved[0]["people"]["kid"]["manual"]["last_action"],
            "manual_home",
        )
        self.now = self.now.replace(minute=1)
        await away.async_press()
        self.assertEqual(self.engine.state("kid"), State.AWAY)
        self.assertEqual(len(self.store.saved), 2)
        self.assertEqual(
            self.store.saved[1]["people"]["kid"]["manual"]["last_action"],
            "manual_away",
        )

    async def test_person_without_backpack_can_use_both_buttons(self):
        home = next(e for e in self.entities
                    if e.person == "adult" and e.target == State.HOME)
        await home.async_press()
        self.assertEqual(self.engine.state("adult"), State.HOME)



if __name__ == "__main__":
    unittest.main()
