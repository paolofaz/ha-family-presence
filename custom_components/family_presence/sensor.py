"""Explicitly named read-only shadow diagnostics; NEVER use for alarm YAML."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShadowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Expose one diagnostically marked shadow sensor per configured person."""
    engine = entry.runtime_data.engine
    async_add_entities(
        ShadowPersonSensor(entry.entry_id, engine, person_id)
        for person_id in engine.people
    )


class ShadowPersonSensor(SensorEntity):
    """Untrusted simulated state, intentionally separate from live YAML outputs."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:account-question"

    def __init__(self, entry_id: str, engine: ShadowCoordinator, person: str) -> None:
        self.engine = engine
        self.person = person
        self._attr_name = f"Family Presence Shadow {engine.people[person].name}"
        self._attr_unique_id = f"{entry_id}_{person}_shadow"

    @property
    def native_value(self) -> str | None:
        state = self.engine.state(self.person)
        return state.value if state is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        """Include provenance and conflicts, not Bluetooth identity or secrets."""
        p = self.engine.people[self.person]
        rt = self.engine.runtime[self.person]
        bag = self.engine._read(p.bag) if p.bag else None
        legacy = self.engine._read(p.reference) if p.reference else None
        return {
            "mode": "shadow_only",
            "do_not_use_for_automations": True,
            "reason": rt.last_reason,
            "last_transition": rt.last_changed.isoformat() if rt.last_changed else None,
            "near_home_since": (
                rt.near_home_entered_at.isoformat() if rt.near_home_entered_at else None
            ),
            "restored_from_storage": rt.restored_from_storage,
            "bag_state": bag,
            "bag_policy": p.bag_policy.value,
            "legacy_state": legacy,
            "matches_legacy": (
                rt.state.value == legacy
                if rt.state is not None and legacy in ("home", "away", "near_home")
                else None
            ),
            "last_blocked_event": rt.last_blocked_event.value if rt.last_blocked_event else None,
            "last_blocked_at": rt.last_blocked_at.isoformat() if rt.last_blocked_at else None,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe after Home Assistant has added the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.engine.async_add_listener(self._shadow_updated))

    @callback
    def _shadow_updated(self, person: str) -> None:
        if person == self.person:
            self.async_write_ha_state()
