"""Read-only shadow-mode coordinator; no Home Assistant imports or writes."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Awaitable, Callable

from .fsm import BagPolicy, BagStatus, Decision, Event, Evidence, State, decide, recent_before, school_bag_window


@dataclass(frozen=True, slots=True)
class Windows:
    exit_gate_seconds: int = 120
    exit_door_seconds: int = 90
    exit_lock_seconds: int = 90
    entry_gate_seconds: int = 120
    entry_door_seconds: int = 120
    entry_lock_seconds: int = 120
    watch_on_delay_seconds: float = 2.0


@dataclass(frozen=True, slots=True)
class PersonSources:
    key: str
    name: str
    iphone: str | None = None
    watch: str | None = None
    bag: str | None = None
    reference: str | None = None
    bag_policy: BagPolicy = BagPolicy.ALWAYS


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    person: str
    event: Event
    previous: State | None
    current: State
    reason: str
    when: datetime
    reference: State | None


@dataclass(frozen=True, slots=True)
class ShadowBlocked:
    person: str
    event: Event
    when: datetime
    reference: State | None


@dataclass(slots=True)
class PersonRuntime:
    state: State | None = None
    last_reason: str | None = None
    last_changed: datetime | None = None
    last_blocked_event: Event | None = None
    last_blocked_at: datetime | None = None
    decisions: list[ShadowDecision] = field(default_factory=list)
    source_revision: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def parse_state(raw: str | None) -> State | None:
    try:
        return State(raw)
    except (ValueError, TypeError):
        return None


def bag_status(raw: str | None, configured: bool) -> BagStatus:
    if not configured:
        return BagStatus.NOT_CONFIGURED
    if raw == "on":
        return BagStatus.PRESENT
    if raw == "off":
        return BagStatus.ABSENT
    return BagStatus.UNKNOWN


def _aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return ts.astimezone(timezone.utc)


class ShadowCoordinator:
    """Independent FSM/lock per person; source adapter owns event validation."""

    def __init__(
        self,
        people: list[PersonSources],
        *,
        read_state: Callable[[str], str | None],
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        windows: Windows = Windows(),
        alarm: str | None = None,
        local_timezone: tzinfo = timezone.utc,
        report: Callable[[ShadowDecision], None] | None = None,
        report_block: Callable[[ShadowBlocked], None] | None = None,
    ) -> None:
        self.people = {p.key: p for p in people}
        if len(self.people) != len(people):
            raise ValueError("Person identifiers must be unique")
        self.runtime: dict[str, PersonRuntime] = {
            p.key: PersonRuntime(state=parse_state(read_state(p.reference)) if p.reference else None)
            for p in people
        }
        self._physical: dict[str, datetime] = {}
        self._read = read_state
        self._clock = clock
        self._sleep = sleep
        self.windows = windows
        self.alarm = alarm
        self.local_timezone = local_timezone
        self.report = report
        self.report_block = report_block

    def note_person_event(self, person: str) -> int:
        """Monotonic per-person revision. Called synchronously on HA callback."""
        runtime = self.runtime[person]
        runtime.source_revision += 1
        return runtime.source_revision

    def record_physical(self, kind: str, at: datetime) -> None:
        """Only record verified gate/door/lock transitions, never a restored state."""
        if kind not in ("gate", "door_open", "door_close", "unlock", "locked"):
            raise ValueError("Invalid physical event kind")
        when = _aware_utc(at)
        previous = self._physical.get(kind)
        if previous is None or when >= previous:
            self._physical[kind] = when

    def _recent(self, key: str, reference: datetime, seconds: int) -> bool:
        return recent_before(reference, self._physical.get(key), seconds)

    def _evidence(self, config: PersonSources, reference: datetime, *, kind: str | None) -> Evidence:
        status = bag_status(self._read(config.bag) if config.bag else None, bool(config.bag))
        phone = self._read(config.iphone) if config.iphone else None
        iphone_outside = bool(config.iphone) and phone not in (None, "home", "unknown", "unavailable")
        return Evidence(
            iphone_outside=iphone_outside,
            gate_exit=self._recent("gate", reference, self.windows.exit_gate_seconds),
            door_closed_exit=self._recent("door_close", reference, self.windows.exit_door_seconds),
            lock_exit=self._recent("locked", reference, self.windows.exit_lock_seconds),
            alarm_armed_away=bool(self.alarm) and self._read(self.alarm) == "armed_away",
            door_open_entry=self._recent("door_open", reference, self.windows.entry_door_seconds),
            door_unlock_entry=self._recent("unlock", reference, self.windows.entry_lock_seconds),
            gate_entry=self._recent("gate", reference, self.windows.entry_gate_seconds),
            watch_detected=bool(config.watch) and self._read(config.watch) == "on",
            physical_event_label={"gate": "gate", "door_open": "door opened", "unlock": "lock unlocked"}.get(kind, "physical event"),
            bag_status=status,
            school_bag_window=school_bag_window(self._clock().astimezone(self.local_timezone)),
        )

    async def process(
        self,
        person: str,
        event: Event,
        *,
        event_time: datetime,
        revision: int | None = None,
        last_seen_before_off: datetime | None = None,
        physical_kind: str | None = None,
    ) -> ShadowDecision | None:
        """Evaluate one event and update only in-memory shadow state."""
        at = _aware_utc(event_time)
        config = self.people[person]
        rt = self.runtime[person]
        async with rt.lock:
            if event == Event.WATCH_SEEN:
                await self._sleep(self.windows.watch_on_delay_seconds)
                # Recheck both revision and live watch state after 2 seconds.
                if (revision is not None and revision != rt.source_revision) or (
                    not config.watch or self._read(config.watch) != "on"
                ):
                    return None

            # OFF physical correlation must use last_seen_before_off, not the
            # notification receipt time. Missing last_seen = no physical match.
            if event == Event.WATCH_LOST and last_seen_before_off is not None:
                reference = _aware_utc(last_seen_before_off)
            elif event == Event.WATCH_LOST:
                reference = None
            else:
                reference = _aware_utc(self._clock())
            evidence = self._evidence(config, reference or at, kind=physical_kind)
            if reference is None and event == Event.WATCH_LOST:
                evidence = Evidence(
                    iphone_outside=evidence.iphone_outside,
                    alarm_armed_away=evidence.alarm_armed_away,
                    bag_status=evidence.bag_status,
                )

            # Bag PRESENT never locks HOME; only the rising OFF->ON event
            # transitions to HOME. ABSENT vetoes every positive source.
            if (
                config.bag_policy == BagPolicy.ALWAYS
                and evidence.bag_status == BagStatus.ABSENT
                and event in (Event.IPHONE_ARRIVED, Event.WATCH_SEEN, Event.PHYSICAL_ENTRY, Event.BAG_ARRIVED)
            ):
                rt.last_blocked_event = event
                rt.last_blocked_at = _aware_utc(self._clock())
                if self.report_block:
                    self.report_block(ShadowBlocked(
                        person=person, event=event, when=rt.last_blocked_at,
                        reference=parse_state(self._read(config.reference)) if config.reference else None,
                    ))

            result: Decision | None = decide(rt.state, event, evidence, bag_policy=config.bag_policy)
            if result is None:
                return None
            previous = rt.state
            rt.state = result.state
            rt.last_reason = result.reason
            when = _aware_utc(self._clock())
            if result.state != previous:
                rt.last_changed = when
            decision = ShadowDecision(
                person=person,
                event=event,
                previous=previous,
                current=result.state,
                reason=result.reason,
                when=when,
                reference=parse_state(self._read(config.reference)) if config.reference else None,
            )
            rt.decisions.append(decision)
            if len(rt.decisions) > 100:
                del rt.decisions[:-100]
            if self.report:
                self.report(decision)
            return decision

    async def reconcile(self) -> list[ShadowDecision]:
        """Never synthesize arrival events when restoring/restarting."""
        decisions = []
        for person in self.people:
            decision = await self.process(person, Event.RECONCILE, event_time=self._clock())
            if decision is not None:
                decisions.append(decision)
        return decisions

    def state(self, person: str) -> State | None:
        return self.runtime[person].state

    def all_away(self) -> bool | None:
        """Unknown member presence never produces a positive all-away verdict."""
        values = [rt.state for rt in self.runtime.values()]
        if not values or any(value is None for value in values):
            return None
        return all(value == State.AWAY for value in values)
