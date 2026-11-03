"""Read-only parity report between shadow FSM and configured legacy helpers.

The existing YAML's Casa certamente vuota template is the AND of four
`input_select.presenza_*` states equalling `away`. This module applies the
equivalent rule to *configured comparison helpers* only. It never reads
or writes the production binary sensor, and cannot affect shadow decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .fsm import State

if TYPE_CHECKING:
    from .coordinator import ShadowCoordinator


@dataclass(frozen=True, slots=True)
class LegacyComparison:
    """Source-complete, side-effect-free, member-aware parity snapshot."""

    status: str
    shadow_all_away: bool
    legacy_expected_all_away: bool | None
    aggregate_matches_legacy: bool | None
    legacy_member_states: dict[str, str | None]
    differing_members: tuple[str, ...]
    missing_reference_members: tuple[str, ...]
    unavailable_reference_members: tuple[str, ...]


def compare_legacy(engine: ShadowCoordinator) -> LegacyComparison:
    """Compare without inventing a legacy value if reference mapping is missing.

    A reference is usable only if its current value is a valid YAML FSM state.
    Missing/unavailable references cannot support a comparison conclusion.
    If all references are valid, both aggregate and individual states are
    checked, to expose member swaps even when the aggregate is unchanged.
    """
    missing: list[str] = []
    unavailable: list[str] = []
    differing: list[str] = []
    legacy_states: dict[str, str | None] = {}

    for key, person in engine.people.items():
        if not person.reference:
            missing.append(key)
            legacy_states[key] = None
            continue
        raw = engine._read(person.reference)
        if raw not in (State.HOME.value, State.AWAY.value, State.NEAR_HOME.value):
            unavailable.append(key)
            legacy_states[key] = raw
            continue
        legacy_states[key] = raw
        current = engine.state(key)
        if current is None or current.value != raw:
            differing.append(key)

    shadow_all_away = engine.all_away()
    legacy_expected: bool | None = None
    aggregate_match: bool | None = None
    if missing:
        status = "not_configured"
    elif unavailable or not engine.people:
        status = "reference_unavailable"
    else:
        legacy_expected = all(
            value == State.AWAY.value for value in legacy_states.values()
        )
        aggregate_match = shadow_all_away == legacy_expected
        if not aggregate_match:
            status = "aggregate_divergence"
        elif differing:
            status = "member_divergence"
        else:
            status = "aligned"

    return LegacyComparison(
        status=status,
        shadow_all_away=shadow_all_away,
        legacy_expected_all_away=legacy_expected,
        aggregate_matches_legacy=aggregate_match,
        legacy_member_states=legacy_states,
        differing_members=tuple(differing),
        missing_reference_members=tuple(missing),
        unavailable_reference_members=tuple(unavailable),
    )
