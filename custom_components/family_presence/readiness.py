"""Read-only, conservative household assessment for the shadow FSM.

This is *not* a production vacancy detector. It never reads the legacy YAML
for decisions and never makes actuator calls. Candidate empty does not mean
that the current sensors have been field-validated for alarm use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .fsm import State

if TYPE_CHECKING:
    from .coordinator import ShadowCoordinator


@dataclass(frozen=True, slots=True)
class HouseholdAssessment:
    """Explanatory result for a diagnostic sensor, never a control command."""

    status: str
    reasons: dict[str, str]
    indicated_present: tuple[str, ...]
    unresolved: tuple[str, ...]
    divergent: tuple[str, ...]


def assess_household(engine: ShadowCoordinator) -> HouseholdAssessment:
    """Classify a household without trusting manual AWAY or restored state.

    Live contradictory phone/Watch readings block the all-away candidate.
    A bag being present is not itself proof that the person is home, but when
    no phone indicates outside, its presence cannot confirm emptiness.
    """
    reasons: dict[str, str] = {}
    indicated_present: list[str] = []
    unresolved: list[str] = []
    divergent: list[str] = []

    for key, p in engine.people.items():
        rt = engine.runtime[key]
        if engine._comparison_status(key) == "diverged":
            divergent.append(key)

        if rt.state is None:
            reason = "stato_sconosciuto"
        elif rt.restored_from_storage:
            reason = "stato_ripristinato_non_verificato"
        elif rt.state in (State.HOME, State.NEAR_HOME):
            reason = (
                "home_manuale_indicato" if rt.state_origin == "manual_force"
                else "presenza_rilevata"
            )
            indicated_present.append(key)
        elif rt.state_origin == "manual_force":
            # Pressing "force away" does not establish physical departure.
            reason = "away_manuale_non_verificato"
        else:
            iphone = engine._read(p.iphone) if p.iphone else None
            watch = engine._read(p.watch) if p.watch else None
            bag = engine._read(p.bag) if p.bag and p.bag_schedule.enabled else None
            phone_healthy = iphone is not None and iphone not in ("unknown", "unavailable")
            phone_outside = phone_healthy and iphone != "home"
            watch_healthy = watch in ("on", "off")
            bag_healthy = bag in ("on", "off")

            if iphone == "home":
                reason = "iphone_segnala_casa"
            elif watch == "on":
                reason = "watch_rilevato_vicino_casa"
            elif bag == "on" and not phone_outside:
                reason = "zaino_presente_senza_conferma_uscita"
            elif not (phone_healthy or watch_healthy or bag_healthy):
                reason = "fonti_non_disponibili"
            else:
                reason = "away_osservato_candidato"

        reasons[key] = reason
        if reason not in (
            "presenza_rilevata", "home_manuale_indicato", "away_osservato_candidato",
        ):
            unresolved.append(key)

    if indicated_present:
        status = "presence_indicated"
    elif engine.people and not unresolved:
        status = "candidate_empty"
    else:
        status = "indeterminate"
    return HouseholdAssessment(
        status=status,
        reasons=reasons,
        indicated_present=tuple(indicated_present),
        unresolved=tuple(unresolved),
        divergent=tuple(divergent),
    )
