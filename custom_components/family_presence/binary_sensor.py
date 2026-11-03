"""Read-only shadow preview of the legacy 'Casa certamente vuota' aggregate.

Never connect this diagnostic binary sensor to production alarm automations.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShadowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Expose the precise on/off result of all configured shadow FSM states."""
    async_add_entities([
        ShadowAllAwayBinarySensor(entry.entry_id, entry.runtime_data.engine)
    ])


class ShadowAllAwayBinarySensor(BinarySensorEntity):
    """ON iff everyone is AWAY, including manually forced or restored AWAY."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:home-export-outline"

    def __init__(self, entry_id: str, engine: ShadowCoordinator) -> None:
        self.engine = engine
        self._attr_name = "Family Presence Shadow - Casa certamente vuota"
        self._attr_unique_id = f"{entry_id}_all_away_shadow"

    @property
    def is_on(self) -> bool:
        return self.engine.all_away()

    @property
    def extra_state_attributes(self) -> dict:
        assessment = self.engine.household_assessment()
        comparison = self.engine.legacy_comparison()
        return {
            "mode": "shadow_only",
            "do_not_use_for_automations": True,
            "not_the_legacy_casa_certamente_vuota": True,
            "aggregation_rule": "all_configured_members_away",
            "legacy_comparison_status": comparison.status,
            "legacy_expected_all_away": comparison.legacy_expected_all_away,
            "aggregate_matches_legacy": comparison.aggregate_matches_legacy,
            "actual_legacy_state": comparison.actual_legacy_state,
            "actual_legacy_all_away": comparison.actual_legacy_all_away,
            "actual_legacy_matches_expected": comparison.actual_legacy_matches_expected,
            "actual_legacy_matches_shadow": comparison.actual_legacy_matches_shadow,
            "legacy_divergence_since": (
                self.engine.parity_diverged_since.isoformat()
                if self.engine.parity_diverged_since else None
            ),
            "legacy_member_states": {
                self.engine.people[key].name: value
                for key, value in comparison.legacy_member_states.items()
            },
            "legacy_differing_members": [
                self.engine.people[key].name for key in comparison.differing_members
            ],
            "legacy_missing_reference_members": [
                self.engine.people[key].name
                for key in comparison.missing_reference_members
            ],
            "legacy_unavailable_reference_members": [
                self.engine.people[key].name
                for key in comparison.unavailable_reference_members
            ],
            "member_states": {
                p.name: (
                    self.engine.state(key).value
                    if self.engine.state(key) is not None else "unknown"
                )
                for key, p in self.engine.people.items()
            },
            "member_reasons": {
                self.engine.people[key].name: reason
                for key, reason in assessment.reasons.items()
            },
            "non_away_members": [
                p.name for key, p in self.engine.people.items()
                if self.engine.state(key) is None
                or self.engine.state(key).value != "away"
            ],
            "source_warnings": {
                self.engine.people[key].name: list(warnings)
                for key, warnings in assessment.source_warnings.items()
            },
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.engine.async_add_listener(self._updated))

    @callback
    def _updated(self, _person: str) -> None:
        self.async_write_ha_state()
