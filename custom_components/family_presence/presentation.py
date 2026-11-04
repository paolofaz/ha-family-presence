"""Presentation profiles with final RC2 output names.

Final is the runtime default. Historical Shadow labels remain internal for
testing identity preservation and upgrading existing entries.

IMPORTANT: changing display names does NOT automatically rename entity_id
in Home Assistant. Unique IDs must stay stable between presentations.
"""
from __future__ import annotations

from dataclasses import dataclass

SHADOW = "shadow"
FINAL = "final"
DEFAULT_PROFILE = FINAL


@dataclass(frozen=True, slots=True)
class Presentation:
    """Human-readable labels and registry-stable identity."""

    name: str
    unique_id: str
    diagnostic: bool


def _check_profile(profile: str) -> None:
    if profile not in (SHADOW, FINAL):
        raise ValueError(f"Unsupported output presentation: {profile}")


def person_presentation(entry_id: str, person_key: str, name: str,
                        profile: str = DEFAULT_PROFILE) -> Presentation:
    _check_profile(profile)
    return Presentation(
        name=(f"Family Presence Shadow {name}"
              if profile == SHADOW else f"Presenza {name}"),
        unique_id=f"{entry_id}_{person_key}_shadow",
        diagnostic=profile == SHADOW,
    )


def aggregate_presentation(entry_id: str,
                           profile: str = DEFAULT_PROFILE) -> Presentation:
    _check_profile(profile)
    return Presentation(
        name=("Family Presence Shadow - Casa certamente vuota"
              if profile == SHADOW else "Casa certamente vuota"),
        unique_id=f"{entry_id}_all_away_shadow",
        diagnostic=profile == SHADOW,
    )


def household_presentation(entry_id: str,
                           profile: str = DEFAULT_PROFILE) -> Presentation:
    _check_profile(profile)
    return Presentation(
        name=("Family Presence Shadow - Diagnostica casa"
              if profile == SHADOW else "Diagnostica presenza"),
        unique_id=f"{entry_id}_household_readiness_shadow",
        diagnostic=True,  # A diagnostic even after final cutover.
    )


def force_presentation(entry_id: str, person_key: str, name: str,
                       target: str, profile: str = DEFAULT_PROFILE) -> Presentation:
    _check_profile(profile)
    if target not in ("home", "away"):
        raise ValueError("A manual button can only force home or away")
    action = "Forza a casa" if target == "home" else "Forza fuori casa"
    prefix = f"Family Presence Shadow {name}" if profile == SHADOW else ""
    return Presentation(
        name=f"{prefix} — {action}" if profile == SHADOW else f"{name} — {action}",
        unique_id=f"{entry_id}_{person_key}_shadow_force_{target}",
        diagnostic=profile == SHADOW,
    )


def preview_final_names(names: tuple[str, ...]) -> dict[str, str]:
    """Preview labels, never claim or reserve actual Home Assistant entity IDs."""
    return {
        **{name: person_presentation("_preview_", name, name, FINAL).name for name in names},
        "casa_certamente_vuota": aggregate_presentation("_preview_", FINAL).name,
    }
