"""Side-effect-free contract for production YAML consumers after cutover.

This module is intentionally NOT connected to Home Assistant services.
Its role is to make the current `familyuscita` and `familyrientro`
conditions explicit and regression-testable before changing any wiring.
"""
from __future__ import annotations

VALID_PRESENCE = frozenset({"home", "near_home", "away"})


def home_certainly_empty(states: tuple[str | None, ...]) -> bool:
    """ON iff each configured member is AWAY; forced AWAY is no exception."""
    return bool(states) and all(state == "away" for state in states)


def should_arm_away(
    *, all_away: bool, lock_state: str | None, alarm_state: str | None
) -> bool:
    """Match YAML familyuscita's three simultaneous state conditions."""
    return bool(all_away) and lock_state == "locked" and alarm_state == "disarmed"


def should_disarm(
    *, previous: str | None, current: str | None, alarm_state: str | None
) -> bool:
    """Match YAML familyrientro: actual away/near_home -> home event only."""
    return (
        previous in ("away", "near_home")
        and current == "home"
        and alarm_state in ("arming", "armed_away")
    )


def should_warn_unlocked_after_delay(
    *, all_away: bool, lock_state: str | None
) -> bool:
    """Match two-minute YAML notification condition (not a door lock action)."""
    return bool(all_away) and lock_state != "locked"
