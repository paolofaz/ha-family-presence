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

    async def test_only_strict_bag_people_get_controls(self):
        self.assertEqual(len(self.entities), 2)
        self.assertEqual(
            {entity.action for entity in self.entities},
            {"confirm_home", "revoke"},
        )
        self.assertTrue(all(e.person == "kid" for e in self.entities))
        self.assertEqual(self.entities[0]._attr_entity_category, "diagnostic")

    async def test_actions_are_explicit_and_persist_immediately(self):
        home = next(x for x in self.entities if x.action == "confirm_home")
        revoke = next(x for x in self.entities if x.action == "revoke")
        self.assertIn("Shadow", home._attr_name)
        self.assertTrue(home.available)
        self.assertFalse(revoke.available)
        await home.async_press()
        self.assertEqual(self.engine.state("kid"), State.HOME)
        self.assertTrue(self.engine.runtime["kid"].manual_home_active)
        self.assertFalse(home.available)
        self.assertTrue(revoke.available)
        self.assertEqual(len(self.store.saved), 1)
        self.assertTrue(
            self.store.saved[0]["people"]["kid"]["manual_home"]["active"]
        )
        await revoke.async_press()
        self.assertIsNone(self.engine.state("kid"))
        self.assertEqual(len(self.store.saved), 2)
        self.assertTrue(
            self.store.saved[1]["people"]["kid"]["manual_home"]["post_manual_ambiguity"]
        )

    async def test_invalid_press_has_no_effect_or_storage_write(self):
        home = next(x for x in self.entities if x.action == "confirm_home")
        self.data["bag"] = "on"
        self.assertFalse(home.available)
        await home.async_press()
        self.assertEqual(len(self.store.saved), 0)
        self.assertIsNone(self.engine.state("kid"))

    async def test_button_receives_entity_updates(self):
        home = next(x for x in self.entities if x.action == "confirm_home")
        await home.async_added_to_hass()
        self.engine.notify_source_update("kid")
        self.assertTrue(home._wrote_state)
        home._unsubscribe()
        self.assertFalse(self.engine._listeners)


if __name__ == "__main__":
    unittest.main()
