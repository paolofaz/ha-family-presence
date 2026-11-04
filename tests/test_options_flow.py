"""Exercise options flow without importing Home Assistant or voluptuous.

Fake framework methods only render forms / capture submitted values; the real
family_presence config-flow control path is executed unmodified.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "family_presence"


def load_flow():
    vol = types.ModuleType("voluptuous")
    vol.Required = lambda key, default=None: key
    vol.Optional = lambda key, default=None: key
    vol.Schema = lambda data: data
    vol.In = lambda items: items
    vol.Coerce = lambda typ: typ
    vol.Range = lambda **kwargs: kwargs
    vol.All = lambda *items: items

    ha = types.ModuleType("homeassistant")
    entries = types.ModuleType("homeassistant.config_entries")

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)

    class OptionsFlowWithReload:
        def async_show_menu(self, *, step_id, menu_options):
            return {"type": "menu", "step_id": step_id, "menu_options": menu_options}

        def async_show_form(
            self, *, step_id, data_schema, errors=None, description_placeholders=None
        ):
            return {
                "type": "form", "step_id": step_id, "schema": data_schema,
                "errors": errors, "description_placeholders": description_placeholders,
            }

        def async_create_entry(self, *, data):
            return {"type": "create_entry", "data": data}

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    # Reuse the same fake UI methods for the ConfigFlow reconfigure steps.
    for method in ("async_show_menu", "async_show_form", "async_create_entry", "async_abort"):
        setattr(ConfigFlow, method, getattr(OptionsFlowWithReload, method))

    def _get_reconfigure_entry(self):
        return self._reconfigure_entry

    async def async_set_unique_id(self, value):
        self._unique_id = value

    def _abort_if_unique_id_mismatch(self):
        self._checked_unique_id = True

    def async_update_reload_and_abort(self, entry, *, data_updates):
        entry.data = {**entry.data, **data_updates}
        return {"type": "abort", "reason": "reconfigure_successful",
                "data": entry.data, "reloaded": True}

    def add_suggested_values_to_schema(self, schema, data):
        return schema

    ConfigFlow._get_reconfigure_entry = _get_reconfigure_entry
    ConfigFlow.async_set_unique_id = async_set_unique_id
    ConfigFlow._abort_if_unique_id_mismatch = _abort_if_unique_id_mismatch
    ConfigFlow.async_update_reload_and_abort = async_update_reload_and_abort
    ConfigFlow.add_suggested_values_to_schema = add_suggested_values_to_schema

    entries.ConfigFlow = ConfigFlow
    entries.OptionsFlowWithReload = OptionsFlowWithReload
    ha.config_entries = entries

    core = types.ModuleType("homeassistant.core")
    core.callback = lambda value: value
    flow = types.ModuleType("homeassistant.data_entry_flow")
    flow.FlowResult = dict
    helpers = types.ModuleType("homeassistant.helpers")
    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.EntitySelectorConfig = lambda **kwargs: kwargs
    selector.EntitySelector = lambda config: config
    selector.TimeSelector = lambda: "time_selector"
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    selector.SelectSelector = lambda config: config

    modules = {
        "voluptuous": vol,
        "homeassistant": ha,
        "homeassistant.config_entries": entries,
        "homeassistant.core": core,
        "homeassistant.data_entry_flow": flow,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.selector": selector,
    }
    name = "custom_components.family_presence.config_flow"
    with patch.dict(sys.modules, modules):
        module = types.ModuleType(name)
        module.__package__ = "custom_components.family_presence"
        spec = importlib.util.spec_from_file_location(name, COMPONENT / "config_flow.py")
        module.__spec__ = spec
        spec.loader.exec_module(module)
    return module, OptionsFlowWithReload


class OptionsFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module, self.base = load_flow()
        self.people = [
            {
                "person_id": "child-id",
                "person_name": "Child",
                "bag_sensor": "binary_sensor.bag",
                "iphone_tracker": "device_tracker.iphone",
                "bag_policy": "always",
            },
            {
                "person_id": "adult-id",
                "person_name": "Adult",
                "iphone_tracker": "device_tracker.other",
            },
        ]
        self.options = {
            "entry_gate_seconds": 123,
            "bag_policies": {"child-id": "legacy"},
        }

    def new(self, people=None, options=None):
        entry = types.SimpleNamespace(
            data={"people": self.people if people is None else people},
            options=self.options if options is None else options,
        )
        flow = self.module.FamilyPresenceOptionsFlow()
        flow.config_entry = entry
        return flow

    async def test_options_use_reload_helper_and_menu_is_small(self):
        flow = self.new()
        self.assertIsInstance(flow, self.base)
        menu = await flow.async_step_init()
        self.assertEqual(menu["menu_options"], ["windows", "bag_person"])

    async def test_no_bag_hides_bag_editor(self):
        flow = self.new(people=[self.people[1]])
        menu = await flow.async_step_init()
        self.assertEqual(menu["menu_options"], ["windows"])

    async def test_windows_preserve_existing_bag_preferences(self):
        flow = self.new()
        form = await flow.async_step_windows()
        self.assertEqual(form["step_id"], "windows")
        self.assertEqual(set(form["schema"]), {
            "exit_gate_seconds", "exit_door_seconds", "exit_lock_seconds",
            "entry_gate_seconds", "entry_door_seconds", "entry_lock_seconds",
        })
        result = await flow.async_step_windows({"exit_gate_seconds": 230})
        self.assertEqual(result["data"]["exit_gate_seconds"], 230)
        self.assertEqual(result["data"]["bag_policies"], {"child-id": "legacy"})

    async def test_person_selection_shows_only_members_with_bags(self):
        flow = self.new()
        choice_form = await flow.async_step_bag_person()
        self.assertEqual(choice_form["schema"]["person"], {"child-id": "Child"})
        result = await flow.async_step_bag_person({"person": "child-id"})
        self.assertEqual(result["step_id"], "bag_schedule")
        self.assertEqual(result["description_placeholders"]["person"], "Child")

    async def test_schedule_form_shows_enabled_hours_and_weekdays(self):
        flow = self.new()
        await flow.async_step_bag_person({"person": "child-id"})
        form = await flow.async_step_bag_schedule()
        self.assertEqual(form["step_id"], "bag_schedule")
        self.assertEqual(set(form["schema"]), {"enabled", "start", "end", "days"})

    async def test_schedule_update_preserves_other_options_and_persons(self):
        flow = self.new()
        await flow.async_step_bag_person({"person": "child-id"})
        result = await flow.async_step_bag_schedule({
            "enabled": True, "start": "00:00", "end": "00:00",
            "days": ["0", "1", "2", "3", "4", "5", "6"],
        })
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["entry_gate_seconds"], 123)
        self.assertEqual(result["data"]["bag_policies"], {"child-id": "legacy"})
        entry = result["data"]["bag_schedules"]["child-id"]
        self.assertEqual(entry["start"], "00:00")
        self.assertEqual(entry["end"], "00:00")
        self.assertEqual(entry["days"], list(range(7)))

    async def test_schedule_can_disable_backpack(self):
        flow = self.new()
        await flow.async_step_bag_person({"person": "child-id"})
        result = await flow.async_step_bag_schedule({
            "enabled": False, "start": "07:00",
            "end": "09:10", "days": ["0", "1", "2", "3", "4"],
        })
        self.assertFalse(result["data"]["bag_schedules"]["child-id"]["enabled"])

    async def test_cannot_edit_person_without_bag(self):
        flow = self.new()
        result = await flow.async_step_bag_person({"person": "adult-id"})
        self.assertEqual(result["errors"]["base"], "invalid_person")
        self.assertEqual((await flow.async_step_bag_schedule())["type"], "abort")

    async def test_legacy_name_based_entries_are_still_editable(self):
        person = {"person_name": "Member", "bag_sensor": "binary_sensor.zaino"}
        flow = self.new(people=[person], options={})
        selection = await flow.async_step_bag_person()
        self.assertEqual(selection["schema"]["person"], {"member": "Member"})
        await flow.async_step_bag_person({"person": "member"})
        result = await flow.async_step_bag_schedule({
            "enabled": True, "start": "07:00", "end": "09:10",
            "days": ["0", "1", "2", "3", "4"],
        })
        self.assertEqual(result["data"]["bag_schedules"]["member"]["days"], [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
