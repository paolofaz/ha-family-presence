"""Build an opt-in, anonymized debugging report without Home Assistant imports.

Never include human names, entity IDs, BLE addresses, GPS coordinates, or
zone names. The user explicitly downloads this report from HA diagnostics.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from .fsm import State
from .labels import reason_label


def _iso(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


def _iphone_status(raw: str | None) -> str:
    if raw in (None, "unknown", "unavailable"):
        return "unavailable"
    return "home" if raw == "home" else "outside_home"


def _binary_status(raw: str | None) -> str:
    return raw if raw in ("on", "off") else "unavailable"


def build_diagnostics(engine, access_history=None) -> dict:
    """Create JSON-safe diagnostics with stable anonymous per-person labels."""
    members = []
    restored_count = 0
    for index, (key, person) in enumerate(engine.people.items(), start=1):
        rt = engine.runtime[key]
        restored_count += bool(rt.restored_from_storage)
        sources = {}
        if person.iphone:
            sources["iphone"] = _iphone_status(engine._read(person.iphone))
        if person.watch:
            sources["watch"] = _binary_status(engine._read(person.watch))
        if person.bag:
            sources["bag"] = _binary_status(engine._read(person.bag))

        member = {
            "id": f"persona_{index}",
            "state": rt.state.value if rt.state is not None else None,
            "reason": reason_label(rt.last_reason),
            "last_transition": _iso(rt.last_changed),
            "state_origin": rt.state_origin,
            "restored_unverified": rt.restored_from_storage,
            "bag_return_eligible": (
                bool(rt.bag_return_eligible and person.bag_schedule.enabled)
                if person.bag else None
            ),
            "near_home_since": _iso(rt.near_home_entered_at),
            "sources": sources,
            "last_ignored_event": (
                rt.last_ignored_event.value if rt.last_ignored_event else None
            ),
            "last_ignored_reason": rt.last_ignored_reason,
            "last_ignored_at": _iso(rt.last_ignored_at),
            "ignored_count": rt.ignored_count,
            "recent_events": [
                {
                    "event": item["event"],
                    "outcome": item["outcome"],
                    "state": item["state"],
                    "at": item["at"],
                    "reason": reason_label(item["reason"]),
                }
                for item in rt.recent_events[-12:]
            ],
        }
        if person.bag:
            member["bag_schedule"] = person.bag_schedule.to_dict()
        members.append(member)

    history = {}
    if access_history is not None:
        # The display Store may contain real entity IDs. Aggregate by event
        # kind rather than exporting those source identifiers.
        for kind, readings in access_history._events.items():
            history[kind] = {
                "configured_sources": len(access_history.allowed[kind]),
                "observed_sources": len(readings),
                "last_at": _iso(max(readings.values())) if readings else None,
            }

    assessment = engine.household_assessment()
    return {
        "report_format": 1,
        "version": "1.0.1",
        "privacy": "Anonymized people and source identifiers; includes event timestamps",
        "household": {
            "all_away": engine.all_away(),
            "status": assessment.status,
            "configured_members": len(engine.people),
            "restored_unverified_members": restored_count,
        },
        "correlation_windows": asdict(engine.windows),
        "members": members,
        "recent_physical_events": {
            kind: _iso(at) for kind, at in sorted(engine._physical.items())
        },
        "access_history": history,
    }
