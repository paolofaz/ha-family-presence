"""Explicitly named read-only shadow diagnostics; NEVER use for alarm YAML."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShadowCoordinator
from .labels import reason_label


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Expose one diagnostically marked shadow sensor per configured person."""
    engine = entry.runtime_data.engine
    async_add_entities([
        *(ShadowPersonSensor(entry.entry_id, engine, person_id)
          for person_id in engine.people),
        ShadowHouseholdSensor(entry.entry_id, engine),
    ])


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
            "reason": reason_label(rt.last_reason),
            "reason_origin": rt.reason_origin,
            "state_origin": rt.state_origin,
            "last_transition": rt.last_changed.isoformat() if rt.last_changed else None,
            "near_home_since": (
                rt.near_home_entered_at.isoformat() if rt.near_home_entered_at else None
            ),
            "restored_from_storage": rt.restored_from_storage,
            "manual_last_action": rt.manual_last_action,
            "manual_last_action_at": (
                rt.manual_last_action_at.isoformat()
                if rt.manual_last_action_at else None
            ),
            "bag_state": bag,
            "bag_enabled": p.bag_schedule.enabled if p.bag else None,
            "bag_window_start": p.bag_schedule.start if p.bag else None,
            "bag_window_end": p.bag_schedule.end if p.bag else None,
            "bag_days": list(p.bag_schedule.days) if p.bag else None,
            "legacy_state": legacy,
            "matches_legacy": (
                rt.state.value == legacy
                if rt.state is not None and legacy in ("home", "away", "near_home")
                else None
            ),
            "comparison_status": self.engine._comparison_status(self.person),
            "divergence_since": (
                rt.divergence_since.isoformat() if rt.divergence_since else None
            ),
            "last_ignored_event": (
                rt.last_ignored_event.value if rt.last_ignored_event else None
            ),
            "last_ignored_reason": rt.last_ignored_reason,
            "last_ignored_at": (
                rt.last_ignored_at.isoformat() if rt.last_ignored_at else None
            ),
            "ignored_event_count": rt.ignored_count,
            "recent_events": list(rt.recent_events[-12:]),
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


class ShadowHouseholdSensor(SensorEntity):
    """Explain the aggregate and raw sensor warnings without overriding it."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:home-search-outline"

    def __init__(self, entry_id: str, engine: ShadowCoordinator) -> None:
        self.engine = engine
        self._attr_unique_id = f"{entry_id}_household_readiness_shadow"
        self._attr_name = "Family Presence Shadow - Diagnostica casa"

    @property
    def native_value(self) -> str:
        return self.engine.household_assessment().status

    @property
    def extra_state_attributes(self) -> dict:
        assessment = self.engine.household_assessment()
        comparison = self.engine.legacy_comparison()
        return {
            "mode": "shadow_only",
            "do_not_use_for_automations": True,
            "not_a_production_alarm_entity": True,
            "all_away_internal": self.engine.all_away(),
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
            "legacy_differing_members": [
                self.engine.people[key].name for key in comparison.differing_members
            ],
            "source_warnings": {
                self.engine.people[key].name: list(warnings)
                for key, warnings in assessment.source_warnings.items()
            },
            "member_diagnostics": {
                self.engine.people[key].name: {
                    "state": self.engine.state(key).value
                    if self.engine.state(key) is not None else None,
                    "reason": reason,
                }
                for key, reason in assessment.reasons.items()
            },
            "presence_indicated_members": [
                self.engine.people[key].name for key in assessment.indicated_present
            ],
            "unresolved_members": [
                self.engine.people[key].name for key in assessment.unresolved
            ],
            "divergent_members": [
                self.engine.people[key].name for key in assessment.divergent
            ],
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.engine.async_add_listener(self._updated))

    @callback
    def _updated(self, _person: str) -> None:
        self.async_write_ha_state()
