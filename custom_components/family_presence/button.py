"""One-shot manual controls to force an individual person HOME or AWAY.

No permanent precedence, no alarm/lock/HVAC services and no YAML writes.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .fsm import State
from .devices import household_device_info
from .presentation import SHADOW, force_presentation

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Expose two explicit actions for every configured member."""
    runtime = entry.runtime_data
    async_add_entities(
        ShadowForceButton(entry.entry_id, runtime, person, state)
        for person in runtime.engine.people
        for state in (State.HOME, State.AWAY)
    )


class ShadowForceButton(ButtonEntity):
    """One event in the FSM: a later sensor event can freely change state."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str, runtime, person: str, target: State) -> None:
        self.runtime = runtime
        self.engine = runtime.engine
        self.person = person
        self.target = target
        name = self.engine.people[person].name
        self.profile = getattr(runtime, "profile", SHADOW)
        presentation = force_presentation(entry_id, person, name, target.value, self.profile)
        self._attr_unique_id = presentation.unique_id
        self._attr_name = presentation.name
        self._attr_has_entity_name = True
        self._attr_device_info = household_device_info(entry_id)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if presentation.diagnostic else None
        self._attr_icon = "mdi:home-import-outline" if target == State.HOME else "mdi:home-export-outline"

    async def async_press(self) -> None:
        """Force current FSM state, persist instantly, keep normal FSM active."""
        decision = await self.engine.force_state(self.person, self.target)
        await self.runtime.store.async_save(self.engine.snapshot())
        _LOGGER.warning(
            "[%s][manual] persona=%s stato=%s (l\u0027allarme resta gestito da YAML)",
            self.profile, self.person, decision.current.value,
        )
