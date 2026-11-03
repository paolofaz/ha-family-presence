"""Config flow for one household with configurable input entities per person.

Configuration and reconfiguration only update the shadow integration until release.
"""
from __future__ import annotations
from typing import Any
from uuid import uuid4
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector, EntitySelectorConfig, SelectSelector, SelectSelectorConfig,
    TimeSelector,
)

from .const import (
    CONF_ADD_ANOTHER, CONF_ALARM, CONF_BAG, CONF_BAG_POLICY, CONF_BAG_POLICIES,
    CONF_BAG_SCHEDULES, CONF_BAG_ENABLED, CONF_BAG_START, CONF_BAG_END, CONF_BAG_DAYS,
    CONF_DOOR, CONF_GATE_ENTITIES,
    CONF_HOUSEHOLD_NAME, CONF_IPHONE, CONF_LOCK, CONF_PEOPLE, CONF_PERSON_NAME,
    CONF_PERSON_ID,
    CONF_REFERENCE,
    CONF_WATCH, DEFAULT_WINDOWS, DOMAIN,
)
from .fsm import BagPolicy
from .bag_schedule import BagSchedule, legacy_schedule


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
})
# Source mapping belongs to Reconfigure, behavioral choices to Configure.
PERSON_RECONFIGURE_SCHEMA = vol.Schema({
    vol.Required(CONF_PERSON_NAME): str,
    vol.Optional(CONF_IPHONE): entity("device_tracker"),
    vol.Optional(CONF_WATCH): entity("binary_sensor"),
    vol.Optional(CONF_BAG): entity("binary_sensor"),
    vol.Optional(CONF_REFERENCE): entity("input_select"),
})


def _member_errors(
    candidate: dict[str, Any], others: list[dict[str, Any]]
) -> dict[str, str]:
    """Validate one person's input without relying on Home Assistant state."""
    name = str(candidate.get(CONF_PERSON_NAME, "")).strip()
    if not name:
        return {CONF_PERSON_NAME: "invalid_name"}
    if any(p[CONF_PERSON_NAME].strip().casefold() == name.casefold() for p in others):
        return {CONF_PERSON_NAME: "duplicate_name"}
    sources = (CONF_IPHONE, CONF_WATCH, CONF_BAG)
    if not any(candidate.get(field) for field in sources):
        return {"base": "missing_sources"}
    # Sharing person-specific sources would make two FSMs react as one person.
    if any(
        candidate.get(field) == p.get(field)
        for p in others
        for field in sources
        if candidate.get(field)
    ):
        return {"base": "duplicate_source"}
    return {}


ANOTHER_SCHEMA = vol.Schema({vol.Required(CONF_ADD_ANOTHER, default=False): bool})


class FamilyPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure shared physical inputs and an arbitrary number of people."""
    VERSION = 1

    def __init__(self) -> None:
        self._household: dict[str, Any] = {}
        self._people: list[dict[str, Any]] = []
        self._edit_person_key: str | None = None

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
            errors = _member_errors(user_input, self._people)
            if not errors:
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

    async def _finish_reconfigure(self, updates: dict[str, Any]) -> FlowResult:
        """Keep the one existing config entry and reload only shadow runtime."""
        await self.async_set_unique_id("household")
        self._abort_if_unique_id_mismatch()
        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(), data_updates=updates
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit source mappings and members without deleting the config entry."""
        members = self._get_reconfigure_entry().data[CONF_PEOPLE]
        actions = ["reconfigure_shared", "reconfigure_choose", "reconfigure_add"]
        if len(members) > 1:
            actions.append("reconfigure_remove")
        return self.async_show_menu(
            step_id="reconfigure", menu_options=actions
        )

    async def async_step_reconfigure_shared(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update shared physical sensor mappings, without touching people."""
        entry = self._get_reconfigure_entry()
        shared_fields = (CONF_HOUSEHOLD_NAME, CONF_GATE_ENTITIES, CONF_DOOR,
                         CONF_LOCK, CONF_ALARM)
        if user_input is not None:
            title = user_input[CONF_HOUSEHOLD_NAME].strip()
            if title:
                # The HA reconfigure helper merges data_updates. Explicitly
                # store None for cleared optional entities so old mappings
                # cannot silently survive a user's removal.
                new_shared = {key: user_input.get(key) for key in shared_fields}
                new_shared[CONF_HOUSEHOLD_NAME] = title
                return await self._finish_reconfigure(new_shared)
            return self.async_show_form(
                step_id="reconfigure_shared",
                data_schema=self.add_suggested_values_to_schema(
                    HOUSEHOLD_SCHEMA, entry.data
                ),
                errors={CONF_HOUSEHOLD_NAME: "invalid_name"},
            )
        return self.async_show_form(
            step_id="reconfigure_shared",
            data_schema=self.add_suggested_values_to_schema(
                HOUSEHOLD_SCHEMA, entry.data
            ),
        )

    async def async_step_reconfigure_choose(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose a member by stable internal ID, not by their display name."""
        choices = {
            _person_key(p): p[CONF_PERSON_NAME]
            for p in self._get_reconfigure_entry().data[CONF_PEOPLE]
        }
        if user_input is not None:
            selected = user_input["person"]
            if selected in choices:
                self._edit_person_key = selected
                return await self.async_step_reconfigure_edit()
            return self.async_show_form(
                step_id="reconfigure_choose",
                data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
                errors={"base": "invalid_person"},
            )
        return self.async_show_form(
            step_id="reconfigure_choose",
            data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
        )

    async def async_step_reconfigure_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a member's sensors and name while preserving its identity."""
        entry = self._get_reconfigure_entry()
        original = next(
            (p for p in entry.data[CONF_PEOPLE]
             if _person_key(p) == self._edit_person_key), None
        )
        if original is None:
            return self.async_abort(reason="person_not_found")
        if user_input is not None:
            others = [
                p for p in entry.data[CONF_PEOPLE]
                if _person_key(p) != self._edit_person_key
            ]
            errors = _member_errors(user_input, others)
            if not errors:
                updated = {
                    **{k: v for k, v in user_input.items() if v},
                    CONF_PERSON_NAME: user_input[CONF_PERSON_NAME].strip(),
                    # Upgrade early name-derived keys without changing the key.
                    CONF_PERSON_ID: _person_key(original),
                    CONF_BAG_POLICY: original.get(
                        CONF_BAG_POLICY, BagPolicy.ALWAYS.value
                    ),
                }
                people = [
                    updated if _person_key(p) == self._edit_person_key else p
                    for p in entry.data[CONF_PEOPLE]
                ]
                return await self._finish_reconfigure({CONF_PEOPLE: people})
        else:
            errors = {}
        return self.async_show_form(
            step_id="reconfigure_edit",
            data_schema=self.add_suggested_values_to_schema(
                PERSON_RECONFIGURE_SCHEMA, original
            ),
            errors=errors,
        )

    async def async_step_reconfigure_add(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a member with a new stable identifier."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            errors = _member_errors(user_input, entry.data[CONF_PEOPLE])
            if not errors:
                member = {
                    **{k: v for k, v in user_input.items() if v},
                    CONF_PERSON_NAME: user_input[CONF_PERSON_NAME].strip(),
                    CONF_PERSON_ID: uuid4().hex,
                    # New members use the school-hours schedule by default.
                    # An old policy code is retained only when editing old data.
                }
                return await self._finish_reconfigure({
                    CONF_PEOPLE: [*entry.data[CONF_PEOPLE], member]
                })
        return self.async_show_form(
            step_id="reconfigure_add",
            data_schema=PERSON_RECONFIGURE_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a member; never permit an empty household."""
        entry = self._get_reconfigure_entry()
        members = entry.data[CONF_PEOPLE]
        if len(members) < 2:
            return self.async_abort(reason="last_member")
        choices = {_person_key(p): p[CONF_PERSON_NAME] for p in members}
        if user_input is not None:
            key = user_input["person"]
            if key in choices:
                return await self._finish_reconfigure({
                    CONF_PEOPLE: [p for p in members if _person_key(p) != key]
                })
            errors = {"base": "invalid_person"}
        else:
            errors = {}
        return self.async_show_form(
            step_id="reconfigure_remove",
            data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
            errors=errors,
        )

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
            return await self.async_step_bag_schedule()
        return self.async_show_form(
            step_id="bag_person",
            data_schema=vol.Schema({vol.Required("person"): vol.In(choices)}),
        )

    async def async_step_bag_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure one event-based ON→OFF window; OFF→ON is anytime."""
        key = self._selected_person
        people = {
            _person_key(p): p
            for p in self.config_entry.data[CONF_PEOPLE]
            if p.get(CONF_BAG)
        }
        if key not in people:
            return self.async_abort(reason="person_not_found")
        person = people[key]
        options = self.config_entry.options
        saved = options.get(CONF_BAG_SCHEDULES, {})
        legacy_policy = options.get(CONF_BAG_POLICIES, {}).get(
            key, person.get(CONF_BAG_POLICY, "legacy")
        )
        schedule = (
            BagSchedule.from_dict(saved[key])
            if key in saved else legacy_schedule(legacy_policy)
        )
        if user_input is not None:
            try:
                days = tuple(sorted(set(int(day) for day in user_input[CONF_BAG_DAYS])))
                new_schedule = BagSchedule(
                    enabled=user_input[CONF_BAG_ENABLED],
                    start=user_input[CONF_BAG_START],
                    end=user_input[CONF_BAG_END],
                    days=days,
                )
            except (KeyError, ValueError, TypeError):
                return self.async_show_form(
                    step_id="bag_schedule",
                    data_schema=self._bag_schedule_schema(schedule),
                    errors={"base": "invalid_schedule"},
                )
            return self.async_create_entry(data={
                **options,
                CONF_BAG_SCHEDULES: {**saved, key: new_schedule.to_dict()},
            })
        return self.async_show_form(
            step_id="bag_schedule",
            data_schema=self._bag_schedule_schema(schedule),
            description_placeholders={"person": person[CONF_PERSON_NAME]},
        )

    @staticmethod
    def _bag_schedule_schema(schedule: BagSchedule) -> vol.Schema:
        weekdays = (
            "Lunedì", "Martedì", "Mercoledì", "Giovedì",
            "Venerdì", "Sabato", "Domenica",
        )
        return vol.Schema({
            vol.Required(CONF_BAG_ENABLED, default=schedule.enabled): bool,
            vol.Required(CONF_BAG_START, default=schedule.start): TimeSelector(),
            vol.Required(CONF_BAG_END, default=schedule.end): TimeSelector(),
            vol.Required(
                CONF_BAG_DAYS,
                default=[str(day) for day in schedule.days],
            ): SelectSelector(SelectSelectorConfig(
                options=[
                    {"value": str(day), "label": name}
                    for day, name in enumerate(weekdays)
                ],
                multiple=True,
            )),
        })
