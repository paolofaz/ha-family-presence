"""Config flow for one household with configurable input entities per person.

Only records configuration in the foundation stage: no active FSM listeners.
"""
from __future__ import annotations
from typing import Any
from uuid import uuid4
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_ADD_ANOTHER, CONF_ALARM, CONF_BAG, CONF_BAG_POLICY, CONF_BAG_POLICIES,
    CONF_DOOR, CONF_GATE_ENTITIES,
    CONF_HOUSEHOLD_NAME, CONF_IPHONE, CONF_LOCK, CONF_PEOPLE, CONF_PERSON_NAME,
    CONF_PERSON_ID,
    CONF_REFERENCE,
    CONF_WATCH, DEFAULT_WINDOWS, DOMAIN,
)
from .fsm import BagPolicy


def entity(domain: str) -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain=domain))


HOUSEHOLD_SCHEMA = vol.Schema({
    vol.Required(CONF_HOUSEHOLD_NAME, default="Home"): str,
    vol.Optional(CONF_GATE_ENTITIES): EntitySelector(
        EntitySelectorConfig(domain=["switch", "binary_sensor"], multiple=True)
    ),
    vol.Optional(CONF_DOOR): entity("binary_sensor"),
    vol.Optional(CONF_LOCK): entity("lock"),
    vol.Optional(CONF_ALARM): entity("alarm_control_panel"),
})
PERSON_SCHEMA = vol.Schema({
    vol.Required(CONF_PERSON_NAME): str,
    vol.Optional(CONF_IPHONE): entity("device_tracker"),
    vol.Optional(CONF_WATCH): entity("binary_sensor"),
    vol.Optional(CONF_BAG): entity("binary_sensor"),
    vol.Optional(CONF_REFERENCE): entity("input_select"),
    vol.Optional(CONF_BAG_POLICY, default=BagPolicy.ALWAYS.value): vol.In(
        [BagPolicy.ALWAYS.value, BagPolicy.LEGACY.value]
    ),
})
ANOTHER_SCHEMA = vol.Schema({vol.Required(CONF_ADD_ANOTHER, default=False): bool})


class FamilyPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure shared physical inputs and an arbitrary number of people."""
    VERSION = 1

    def __init__(self) -> None:
        self._household: dict[str, Any] = {}
        self._people: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id("household")
            self._abort_if_unique_id_configured()
            self._household = user_input
            return await self.async_step_person()
        return self.async_show_form(step_id="user", data_schema=HOUSEHOLD_SCHEMA)

    async def async_step_person(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_PERSON_NAME].strip()
            if not name:
                errors[CONF_PERSON_NAME] = "invalid_name"
            elif any(p[CONF_PERSON_NAME].casefold() == name.casefold() for p in self._people):
                errors[CONF_PERSON_NAME] = "duplicate_name"
            elif not any(user_input.get(k) for k in (CONF_IPHONE, CONF_WATCH, CONF_BAG)):
                errors["base"] = "missing_sources"
            else:
                self._people.append({
                    **user_input,
                    CONF_PERSON_NAME: name,
                    CONF_PERSON_ID: uuid4().hex,
                })
                return await self.async_step_another()
        return self.async_show_form(step_id="person", data_schema=PERSON_SCHEMA, errors=errors)

    async def async_step_another(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            if user_input[CONF_ADD_ANOTHER]:
                return await self.async_step_person()
            return self.async_create_entry(
                title=self._household[CONF_HOUSEHOLD_NAME],
                data={**self._household, CONF_PEOPLE: self._people},
            )
        return self.async_show_form(step_id="another", data_schema=ANOTHER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> FamilyPresenceOptionsFlow:
        return FamilyPresenceOptionsFlow()


def _person_key(person: dict[str, Any]) -> str:
    """Stable key for new entries, compatible with early name-based entries."""
    return person.get(CONF_PERSON_ID) or person[CONF_PERSON_NAME].strip().casefold()


class FamilyPresenceOptionsFlow(OptionsFlowWithReload):
    """Edit approved policies and correlation windows, then reload shadow runtime.

    The BLE detection/timeout settings belong to the independent providers,
    not this integration. Person source mapping is deliberately not edited here.
    """

    def __init__(self) -> None:
        self._selected_person: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        actions = ["windows"]
        if any(person.get(CONF_BAG) for person in self.config_entry.data[CONF_PEOPLE]):
            actions.append("bag_person")
        return self.async_show_menu(step_id="init", menu_options=actions)

    async def async_step_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Keep bag overrides when tuning the timestamp windows."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )
        schema = vol.Schema({
            vol.Required(k, default=self.config_entry.options.get(k, v)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=3600)
            )
            for k, v in DEFAULT_WINDOWS.items()
        })
        return self.async_show_form(step_id="windows", data_schema=schema)

    async def async_step_bag_person(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose one person with a configured backpack sensor."""
        choices = {
            _person_key(p): p[CONF_PERSON_NAME]
            for p in self.config_entry.data[CONF_PEOPLE]
            if p.get(CONF_BAG)
        }
        if user_input is not None:
            person_key = user_input["person"]
            if person_key not in choices:
                return self.async_show_form(
                    step_id="bag_person",
                    data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
                    errors={"base": "invalid_person"},
                )
            self._selected_person = person_key
            return await self.async_step_bag_policy()
        return self.async_show_form(
            step_id="bag_person",
            data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
        )

    async def async_step_bag_policy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """One per-person switch: ALWAYS (strict priority) or LEGACY (YAML)."""
        current_person = self._selected_person
        people = {
            _person_key(p): p
            for p in self.config_entry.data[CONF_PEOPLE]
            if p.get(CONF_BAG)
        }
        if current_person not in people:
            return self.async_abort(reason="person_not_found")
        person = people[current_person]
        saved = self.config_entry.options.get(CONF_BAG_POLICIES, {})
        default = saved.get(
            current_person, person.get(CONF_BAG_POLICY, BagPolicy.ALWAYS.value)
        )
        if user_input is not None:
            selection = user_input[CONF_BAG_POLICY]
            if selection not in (BagPolicy.ALWAYS.value, BagPolicy.LEGACY.value):
                return self.async_show_form(
                    step_id="bag_policy",
                    data_schema=vol.Schema({
                        vol.Required(CONF_BAG_POLICY, default=default):
                            vol.In([BagPolicy.ALWAYS.value, BagPolicy.LEGACY.value])
                    }),
                    errors={CONF_BAG_POLICY: "invalid_policy"},
                )
            return self.async_create_entry(data={
                **self.config_entry.options,
                CONF_BAG_POLICIES: {
                    **saved,
                    current_person: selection,
                },
            })
        return self.async_show_form(
            step_id="bag_policy",
            data_schema=vol.Schema({
                vol.Required(CONF_BAG_POLICY, default=default):
                    vol.In([BagPolicy.ALWAYS.value, BagPolicy.LEGACY.value])
            }),
            description_placeholders={"person": person[CONF_PERSON_NAME]},
        )
