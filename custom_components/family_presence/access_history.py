"""Persistent access-event display history; NEVER FSM corroboration evidence.

The coordinator's short-lived _physical timers remain completely separate.
The history contains only validated physical state transitions and is read
by one diagnostic sensor, not by any presence decision rule.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .const import CONF_DOOR, CONF_GATE_ENTITIES, CONF_LOCK


EVENT_NAMES = {
    "gate": "Cancello azionato",
    "door_open": "Porta aperta",
    "door_close": "Porta chiusa",
    "unlock": "Serratura sbloccata",
    "locked": "Serratura bloccata",
}


class AccessHistory:
    """Last confirmed event per source and direction, with bounded storage."""

    def __init__(self, config: dict) -> None:
        gates = set(config.get(CONF_GATE_ENTITIES) or [])
        door = config.get(CONF_DOOR)
        lock = config.get(CONF_LOCK)
        # Use a set to avoid duplicate gate sources in user configuration.
        self.allowed: dict[str, set[str]] = {
            "gate": gates,
            "door_open": {door} if door else set(),
            "door_close": {door} if door else set(),
            "unlock": {lock} if lock and lock not in gates else set(),
            "locked": {lock} if lock and lock not in gates else set(),
        }
        # Gate sources win over the household lock if the same entity was
        # configured in both places (matches the existing adapter priority).
        self._events: dict[str, dict[str, datetime]] = {
            kind: {} for kind in EVENT_NAMES
        }
        self._listeners: set[Callable[[], None]] = set()

    @property
    def has_sources(self) -> bool:
        return any(self.allowed.values())

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def record(self, kind: str, source: str, when: datetime) -> bool:
        """Store only a newer verified event; reject duplicates or stale events."""
        if source not in self.allowed.get(kind, ()):
            return False
        if not isinstance(when, datetime) or when.utcoffset() is None:
            return False
        at = when.astimezone(timezone.utc)
        previous = self._events[kind].get(source)
        if previous is not None and at <= previous:
            return False
        self._events[kind][source] = at
        for callback in tuple(self._listeners):
            callback()
        return True

    def snapshot(self) -> dict:
        """Store only the latest timestamp per configured source/kind."""
        return {
            "format": 1,
            "events": {
                kind: {source: when.isoformat()
                       for source, when in sorted(events.items())}
                for kind, events in self._events.items()
            },
        }

    def restore_snapshot(self, data: object) -> int:
        """Recover display history without ever updating FSM physical evidence."""
        if not isinstance(data, dict) or data.get("format") != 1:
            return 0
        events = data.get("events")
        if not isinstance(events, dict):
            return 0
        restored = 0
        for kind, allowed in self.allowed.items():
            saved = events.get(kind)
            if not isinstance(saved, dict):
                continue
            for source in allowed:
                raw = saved.get(source)
                if not isinstance(raw, str):
                    continue
                try:
                    timestamp = datetime.fromisoformat(raw)
                except ValueError:
                    continue
                if timestamp.utcoffset() is None:
                    continue
                when = timestamp.astimezone(timezone.utc)
                # Direct assignment intentionally emits no callback during boot.
                self._events[kind][source] = when
                restored += 1
        return restored

    @property
    def latest(self) -> tuple[str, str, datetime] | None:
        pairs = [
            (when, kind, source)
            for kind, sources in self._events.items()
            for source, when in sources.items()
        ]
        if not pairs:
            return None
        when, kind, source = max(pairs)
        return kind, source, when

    @property
    def state(self) -> str:
        latest = self.latest
        return EVENT_NAMES[latest[0]] if latest else "Nessun evento"

    @property
    def attributes(self) -> dict:
        """Stable, event-driven attributes; no elapsed-time counters."""
        result: dict = {}
        if self.allowed["gate"]:
            result["cancelli"] = {
                source: self._events["gate"][source].isoformat()
                if source in self._events["gate"] else None
                for source in sorted(self.allowed["gate"])
            }
        if self.allowed["door_open"]:
            for kind, label in (
                ("door_open", "porta_aperta"),
                ("door_close", "porta_chiusa"),
            ):
                result[label] = next(
                    (at.isoformat() for at in self._events[kind].values()),
                    None,
                )
        if self.allowed["unlock"]:
            for kind, label in (
                ("unlock", "serratura_sbloccata"),
                ("locked", "serratura_bloccata"),
            ):
                result[label] = next(
                    (at.isoformat() for at in self._events[kind].values()),
                    None,
                )
        latest = self.latest
        result["ultimo_evento_alle"] = latest[2].isoformat() if latest else None
        result["ultima_sorgente"] = latest[1] if latest else None
        return result
