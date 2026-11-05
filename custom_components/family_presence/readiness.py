"""Aggregate the independent FSM member states without second-guessing them.

The manual force event is authoritative until a later valid FSM event changes
the member state. Raw sensors can raise *diagnostic warnings*, but they cannot
veto the aggregate. This module reads no legacy YAML states for decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .fsm import State

if TYPE_CHECKING:
    from .coordinator import ShadowCoordinator


@dataclass(frozen=True, slots=True)
class HouseholdAssessment:
    """State-only home-empty verdict and independent source diagnostics."""

    all_away: bool
    status: str
    reasons: dict[str, str]
    indicated_present: tuple[str, ...]
    unresolved: tuple[str, ...]
    divergent: tuple[str, ...]
    source_warnings: dict[str, tuple[str, ...]]


def assess_household(engine: ShadowCoordinator) -> HouseholdAssessment:
    """True iff the nonempty household has AWAY for every member.

    Restored AWAY and manually forced AWAY are valid *states* for aggregation.
    Unknown and NEAR_HOME are not AWAY. This matches the legacy YAML template.
    """
    reasons: dict[str, str] = {}
    present: list[str] = []
    unresolved: list[str] = []
    divergent: list[str] = []
    source_warnings: dict[str, tuple[str, ...]] = {}

    for key, person in engine.people.items():
        rt = engine.runtime[key]
        state = rt.state
        if state is State.AWAY:
            reason = (
                "away_forzato" if rt.state_origin == "manual_force"
                else "away_ripristinato" if rt.restored_from_storage
                else "away_fsm"
            )
        elif state is State.HOME:
            reason = "home_forzato" if rt.state_origin == "manual_force" else "home_fsm"
            present.append(key)
        elif state is State.NEAR_HOME:
            reason = "near_home"
            present.append(key)
        else:
            reason = "stato_sconosciuto"
            unresolved.append(key)
        reasons[key] = reason

        if engine._comparison_status(key) == "diverged":
            divergent.append(key)

        # Advisory only; these readings NEVER alter the authoritative verdict.
        # During a verified backpack-caused absence, phone/Watch may correctly
        # have been left charging at home. Do not label that normal family
        # situation as a contradictory presence warning.
        bag_out_trip = (
            state is State.AWAY and bool(person.bag)
            and person.bag_schedule.enabled and rt.bag_return_eligible
            and engine._read(person.bag) == "off"
        )
        warnings: list[str] = []
        if person.iphone:
            iphone = engine._read(person.iphone)
            if state is State.AWAY and iphone == "home" and not bag_out_trip:
                warnings.append("iphone_home_con_fsm_away")
            elif iphone in (None, "unknown", "unavailable"):
                warnings.append("iphone_non_disponibile")
        if person.watch:
            watch = engine._read(person.watch)
            if state is State.AWAY and watch == "on" and not bag_out_trip:
                warnings.append("watch_on_con_fsm_away")
            elif watch in (None, "unknown", "unavailable"):
                warnings.append("watch_non_disponibile")
        if person.bag and person.bag_schedule.enabled:
            bag = engine._read(person.bag)
            if bag in (None, "unknown", "unavailable"):
                warnings.append("zaino_non_disponibile")
        if warnings:
            source_warnings[key] = tuple(warnings)

    all_away = bool(engine.people) and all(
        rt.state is State.AWAY for rt in engine.runtime.values()
    )
    status = (
        "all_away" if all_away
        else "presence_indicated" if present
        else "incomplete"
    )
    return HouseholdAssessment(
        all_away=all_away,
        status=status,
        reasons=reasons,
        indicated_present=tuple(present),
        unresolved=tuple(unresolved),
        divergent=tuple(divergent),
        source_warnings=source_warnings,
    )
