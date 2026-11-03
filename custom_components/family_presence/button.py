"""Explicit, diagnostic-only shadow controls for backpack exceptions.

These buttons mutate ONLY the in-memory shadow FSM + its private snapshot.
No production helper or alarm/lock/heating service calls are made.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .fsm import BagPolicy

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Only strict backpack members have explicit manual exception actions."""
    runtime = entry.runtime_data
    async_add_entities(
        ShadowBagButton(entry.entry_id, runtime, person, action)
        for person, sources in runtime.engine.people.items()
        if sources.bag and sources.bag_policy == BagPolicy.ALWAYS
        for action in ("confirm_home", "revoke")
    )


class ShadowBagButton(ButtonEntity):
    """A deliberate, auditable manual action; never operates real devices."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str, runtime, person: str, action: str) -> None:
        self.runtime = runtime
        self.engine = runtime.engine
        self.person = person
        self.action = action
        name = self.engine.people[person].name
        self._attr_unique_id = f"{entry_id}_{person}_shadow_bag_{action}"
        self._attr_name = (
            f"Family Presence Shadow {name} — Conferma in casa senza zaino"
            if action == "confirm_home"
            else f"Family Presence Shadow {name} — Revoca conferma senza zaino"
        )
        self._attr_icon = (
            "mdi:home-check" if action == "confirm_home"
            else "mdi:home-question"
        )

    @property
    def available(self) -> bool:
        if self.action == "confirm_home":
            return self.engine.manual_home_available(self.person)
        return self.engine.runtime[self.person].manual_home_active

    async def async_press(self) -> None:
        """Commit the manual shadow action and persist it immediately."""
        if self.action == "confirm_home":
            changed = await self.engine.confirm_home_without_bag(self.person)
        else:
            changed = await self.engine.revoke_manual_home(self.person)
        if not changed:
            return
        await self.runtime.store.async_save(self.engine.snapshot())
        _LOGGER.warning(
            "[shadow][manual] persona=%s azione=%s (solo diagnostica; nessun comando alla casa)",
            self.person,
            self.action,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.engine.async_add_listener(self._shadow_updated))

    @callback
    def _shadow_updated(self, person: str) -> None:
        if person == self.person:
            self.async_write_ha_state()
