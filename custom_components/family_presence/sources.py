"""Home Assistant read-only source adapter for the shadow FSM.

Never writes helper entities or invokes alarm/lock/heating services.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from homeassistant.core import Event as HAEvent, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALARM, CONF_BAG, CONF_BAG_POLICY, CONF_BAG_POLICIES,
    CONF_DOOR, CONF_GATE_ENTITIES,
    CONF_IPHONE, CONF_LOCK, CONF_PEOPLE, CONF_PERSON_NAME, CONF_PERSON_ID, CONF_REFERENCE,
    CONF_WATCH,
)
from .coordinator import PersonSources, ShadowBlocked, ShadowCoordinator, ShadowDecision, Windows
from .fsm import BagPolicy, Event

_LOGGER = logging.getLogger(__name__)
_INVALID = frozenset(("unknown", "unavailable"))


def _last_seen(value: Any) -> datetime | None:
    """Read Watch last_seen_before_off, never infer it from OFF receipt time."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = dt_util.parse_datetime(value)
    else:
        return None
    if dt is None or dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _person_specs(
    config: dict[str, Any], options: dict[str, Any] | None = None
) -> list[PersonSources]:
    policies = (options or {}).get(CONF_BAG_POLICIES, {})
    return [
        PersonSources(
            key=p.get(CONF_PERSON_ID) or p[CONF_PERSON_NAME].strip().casefold(),
            name=p[CONF_PERSON_NAME],
            iphone=p.get(CONF_IPHONE),
            watch=p.get(CONF_WATCH),
            bag=p.get(CONF_BAG),
            reference=p.get(CONF_REFERENCE),
            bag_policy=BagPolicy(policies.get(
                p.get(CONF_PERSON_ID) or p[CONF_PERSON_NAME].strip().casefold(),
                p.get(CONF_BAG_POLICY, BagPolicy.ALWAYS.value),
            )),
        )
        for p in config[CONF_PEOPLE]
    ]


def build_coordinator(hass: HomeAssistant, entry: Any) -> ShadowCoordinator:
    """Seed each shadow state from an optional legacy input_select."""
    config, options = entry.data, entry.options
    defaults = Windows()
    window_data = {
        key: int(options.get(key, getattr(defaults, key)))
        for key in (
            "exit_gate_seconds", "exit_door_seconds", "exit_lock_seconds",
            "entry_gate_seconds", "entry_door_seconds", "entry_lock_seconds",
        )
    }

    def read_state(entity_id: str) -> str | None:
        state = hass.states.get(entity_id)
        return state.state if state is not None else None

    def report(d: ShadowDecision) -> None:
        _LOGGER.info(
            "[shadow] %s: %s -> %s via %s (%s); baseline=%s",
            d.person, d.previous, d.current, d.event.value,
            d.reason, d.reference,
        )
        if d.near_home_duration_seconds is not None:
            _LOGGER.info(
                "[shadow][near_home] %s: resolved after %.1f seconds -> %s",
                d.person, d.near_home_duration_seconds, d.current.value,
            )

    def report_block(block: ShadowBlocked) -> None:
        _LOGGER.info(
            "[shadow][blocked] %s: ignored %s because bag is absent; baseline=%s",
            block.person, block.event.value, block.reference,
        )

    return ShadowCoordinator(
        _person_specs(config, options),
        read_state=read_state,
        windows=Windows(**window_data),
        alarm=config.get(CONF_ALARM),
        local_timezone=ZoneInfo(hass.config.time_zone),
        report=report,
        report_block=report_block,
    )


class ShadowSourceAdapter:
    """Validate HA source changes before they reach the pure coordinator."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any], engine: ShadowCoordinator) -> None:
        self._hass = hass
        self.engine = engine
        self._unsub: Any = None
        self._tasks: set[asyncio.Task] = set()
        self._person_inputs: dict[str, list[tuple[str, str]]] = {}
        self._reference_inputs: dict[str, list[str]] = {}
        for p in engine.people.values():
            if p.reference:
                self._reference_inputs.setdefault(p.reference, []).append(p.key)
            for entity, kind in ((p.iphone, "iphone"), (p.watch, "watch"), (p.bag, "bag")):
                if entity:
                    self._person_inputs.setdefault(entity, []).append((p.key, kind))
        self._gates = set(config.get(CONF_GATE_ENTITIES) or [])
        self._door = config.get(CONF_DOOR)
        self._lock = config.get(CONF_LOCK)

    def start(self) -> None:
        entities = set(self._person_inputs) | set(self._reference_inputs) | self._gates
        if self._door:
            entities.add(self._door)
        if self._lock:
            entities.add(self._lock)
        if entities:
            self._unsub = async_track_state_change_event(self._hass, sorted(entities), self._changed)
        _LOGGER.info(
            "Family Presence SHADOW active for %d people; no HA states or devices controlled",
            len(self.engine.people),
        )

    def _schedule(self, coro: Any) -> None:
        task = self._hass.async_create_task(coro, name="family_presence_shadow")
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            _LOGGER.error("Family Presence shadow processing failed", exc_info=error)

    @callback
    def _changed(self, event: HAEvent) -> None:
        entity_id = event.data["entity_id"]
        before = event.data.get("old_state")
        after = event.data.get("new_state")
        if after is None:
            return
        old = before.state if before else None
        new = after.state
        at = event.time_fired
        if old == new:
            return

        # The old YAML helper can change independently of the shadow FSM.
        # Update comparison attributes, but NEVER interpret it as a new event.
        for key in self._reference_inputs.get(entity_id, ()):
            self.engine.notify_source_update(key)
        for key, _kind in self._person_inputs.get(entity_id, ()):
            self.engine.notify_source_update(key)

        # Recovery from unknown/unavailable is NOT a new arrival/departure.
        # But a recovered OFF bag can reconcile the strict absence invariant.
        if old in _INVALID or old is None or new in _INVALID:
            if new == "off" and entity_id in self._person_inputs:
                for key, kind in self._person_inputs[entity_id]:
                    if kind == "bag":
                        revision = self.engine.note_person_event(key)
                        self._schedule(self.engine.process(
                            key, Event.RECONCILE, event_time=at, revision=revision,
                        ))
            return

        physical: str | None = None
        if entity_id in self._gates and (old, new) == ("off", "on"):
            physical = "gate"
        elif entity_id == self._door:
            physical = {("off", "on"): "door_open", ("on", "off"): "door_close"}.get((old, new))
        elif entity_id == self._lock:
            physical = {"locked": "locked", "unlocked": "unlock"}.get(new)

        if physical:
            self.engine.record_physical(physical, at)
            if physical in ("gate", "door_open", "unlock"):
                for key, config in self.engine.people.items():
                    if config.watch:
                        self._schedule(self.engine.process(
                            key, Event.PHYSICAL_ENTRY, event_time=at,
                            physical_kind=physical,
                        ))

        for key, kind in self._person_inputs.get(entity_id, []):
            chosen: Event | None = None
            if kind == "iphone":
                if old == "home" and new != "home":
                    chosen = Event.IPHONE_LEFT
                elif new == "home" and old != "home":
                    chosen = Event.IPHONE_ARRIVED
            elif kind == "watch":
                if (old, new) == ("off", "on"):
                    chosen = Event.WATCH_SEEN
                elif (old, new) == ("on", "off"):
                    chosen = Event.WATCH_LOST
            elif kind == "bag":
                if (old, new) == ("off", "on"):
                    chosen = Event.BAG_ARRIVED
                elif (old, new) == ("on", "off"):
                    chosen = Event.BAG_LEFT
            if chosen is None:
                continue
            revision = self.engine.note_person_event(key)
            self._schedule(self.engine.process(
                key, chosen, event_time=at, revision=revision,
                last_seen_before_off=_last_seen(after.attributes.get("last_seen_before_off"))
                if chosen == Event.WATCH_LOST else None,
            ))

    async def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
