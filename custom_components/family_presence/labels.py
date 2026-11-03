"""Human-facing Italian descriptions; FSM and stored configuration stay stable.

These strings are presentation only. The FSM never makes a decision from
a translated message. Existing alpha snapshots contain English reason values
and are rendered in Italian without discarding their stored provenance.
"""
from __future__ import annotations

from .fsm import BagPolicy

BAG_POLICY_CHOICES_IT = {
    BagPolicy.ALWAYS.value: "Priorità assoluta",
    BagPolicy.LEGACY.value: "Fascia scolastica (lun–ven 07:00–09:10)",
}

_REASON_IT = {
    "Bag absent (priority)": "Zaino assente: priorità assoluta",
    "Bag arrived": "Zaino rientrato",
    "Bag left": "Zaino uscito nella fascia scolastica",
    "iPhone left home zone": "iPhone uscito dalla zona casa",
    "iPhone entered home zone": "iPhone entrato nella zona casa",
    "iPhone outside": "iPhone fuori dalla zona casa",
    "Watch no longer detected before arrival confirmed": "Watch non più rilevato: rientro non confermato",
    "Watch OFF + recent gate before last_seen": "Watch non rilevato: cancello recente prima dell'ultimo avvistamento",
    "Watch OFF + recent door close before last_seen": "Watch non rilevato: porta chiusa prima dell'ultimo avvistamento",
    "Watch OFF + recent lock before last_seen": "Watch non rilevato: serratura chiusa prima dell'ultimo avvistamento",
    "Watch OFF + alarm armed away": "Watch non rilevato: allarme inserito in modalità fuori casa",
    "Watch detected + recent door opening": "Watch rilevato e porta aperta recentemente",
    "Watch detected + recent unlock": "Watch rilevato e serratura sbloccata recentemente",
    "Watch detected + recent gate": "Watch rilevato e cancello aperto recentemente",
    "Watch detected near home": "Watch rilevato nelle vicinanze: rientro da confermare",
    "Watch detected + gate": "Watch rilevato e cancello aperto",
    "Watch detected + door opened": "Watch rilevato e porta aperta",
    "Watch detected + lock unlocked": "Watch rilevato e serratura sbloccata",
    "Watch detected + physical event": "Watch rilevato e ingresso fisico",
}


def reason_label(reason: str | None) -> str | None:
    """Translate all current machine-generated reason strings for Lovelace."""
    if reason is None:
        return None
    return _REASON_IT.get(reason, reason)


def bag_policy_label(policy: BagPolicy) -> str:
    """Show intention, not the backwards-compatible internal option value."""
    return BAG_POLICY_CHOICES_IT.get(policy.value, policy.value)
