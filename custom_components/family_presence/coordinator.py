"""Read-only shadow-mode coordinator; no Home Assistant imports or writes."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Any, Awaitable, Callable

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
    near_home_duration_seconds: float | None = None


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
    # Seeded near_home has unknown age; only newly observed entries have a timer.
    near_home_entered_at: datetime | None = None
    restored_from_storage: bool = False
    # State and reason have different provenance: a live YAML reference can
    # establish state while a compatible snapshot supplies historical *reason*.
    state_origin: str = "unknown"
    reason_origin: str = "not_recorded"
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
            p.key: PersonRuntime(
                state=seed,
                state_origin="legacy_reference" if seed is not None else "unknown",
            )
            for p in people
            for seed in [parse_state(read_state(p.reference)) if p.reference else None]
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
        self._listeners: set[Callable[[str], None]] = set()

    def async_add_listener(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Register local shadow updates for diagnostic entities and storage."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _notify(self, person: str) -> None:
        for listener in tuple(self._listeners):
            listener(person)

    def notify_source_update(self, person: str) -> None:
        """Refresh shadow diagnostics for raw source and legacy helper changes."""
        self._notify(person)

    @staticmethod
    def _fingerprint(person: PersonSources) -> str:
        """Reject snapshots from prior source maps or changed bag policies."""
        mapping = {
            "iphone": person.iphone, "watch": person.watch,
            "bag": person.bag, "reference": person.reference,
            "bag_policy": person.bag_policy.value,
        }
        return hashlib.sha256(
            json.dumps(mapping, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Serializable shadow state only, never BLE observations or keys."""
        return {
            "format": 1,
            "people": {
                key: {
                    "fingerprint": self._fingerprint(self.people[key]),
                    "state": rt.state.value if rt.state is not None else None,
                    "reason": rt.last_reason,
                    "last_changed": rt.last_changed.isoformat() if rt.last_changed else None,
                }
                for key, rt in self.runtime.items()
            },
        }

    def restore_snapshot(self, data: Any) -> int:
        """Restore state and/or diagnostic reason from a compatible snapshot.

        A valid live YAML helper has priority for STATE. If the saved shadow
        state agrees with it, retain the saved cause and timestamp too. A
        disagreeing or reconfigured snapshot must NOT attribute a stale cause
        to the current state. Without a usable YAML reference, the snapshot
        may recover state but is explicitly marked unverified for all-away.

        Physical events and provisional near-home durations NEVER survive
        restart. The return value counts state restored without a reference,
        not diagnostic metadata restored with an agreeing reference.
        """
        if not isinstance(data, dict) or data.get("format") != 1:
            return 0
        people = data.get("people")
        if not isinstance(people, dict):
            return 0
        restored = 0
        for key, rt in self.runtime.items():
            config = self.people[key]
            record = people.get(key)
            if not isinstance(record, dict):
                continue
            if record.get("fingerprint") != self._fingerprint(config):
                continue
            saved_state = parse_state(record.get("state"))
            if saved_state is None:
                continue

            # Seeded from the live reference in __init__: don't replace a
            # known reference state or its occupancy confidence with storage.
            reference_state = rt.state
            if reference_state is not None:
                if saved_state != reference_state:
                    continue  # Saved reason would describe a DIFFERENT state.
                rt.state_origin = "legacy_reference"
                rt.restored_from_storage = False
                reason_origin = "saved_snapshot_matched_legacy"
            else:
                rt.state = saved_state
                rt.state_origin = "saved_shadow_unverified"
                rt.restored_from_storage = True
                reason_origin = "saved_snapshot_unverified"
                restored += 1

            reason = record.get("reason")
            if isinstance(reason, str) and reason.strip():
                rt.last_reason = reason
                rt.reason_origin = reason_origin
            else:
                rt.last_reason = None
                rt.reason_origin = "not_recorded"

            rt.last_changed = None
            ts = record.get("last_changed")
            if isinstance(ts, str):
                try:
                    rt.last_changed = _aware_utc(datetime.fromisoformat(ts))
                except ValueError:
                    pass
            rt.near_home_entered_at = None
        return restored

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
                self._notify(person)

            result: Decision | None = decide(rt.state, event, evidence, bag_policy=config.bag_policy)
            if result is None:
                return None
            previous = rt.state
            rt.state = result.state
            rt.last_reason = result.reason
            rt.restored_from_storage = False
            rt.state_origin = "observed_transition"
            rt.reason_origin = "observed_event"
            when = _aware_utc(self._clock())
            near_home_duration: float | None = None
            if result.state != previous:
                rt.last_changed = when
                if previous == State.NEAR_HOME:
                    if rt.near_home_entered_at is not None:
                        near_home_duration = max(
                            0.0, (when - rt.near_home_entered_at).total_seconds()
                        )
                    rt.near_home_entered_at = None
                if result.state == State.NEAR_HOME:
                    rt.near_home_entered_at = when
            decision = ShadowDecision(
                person=person,
                event=event,
                previous=previous,
                current=result.state,
                reason=result.reason,
                when=when,
                reference=parse_state(self._read(config.reference)) if config.reference else None,
                near_home_duration_seconds=near_home_duration,
            )
            rt.decisions.append(decision)
            if len(rt.decisions) > 100:
                del rt.decisions[:-100]
            if self.report:
                self.report(decision)
            self._notify(person)
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

    def near_home_age_seconds(
        self, person: str, *, now: datetime | None = None
    ) -> float | None:
        """Elapsed seconds in a known provisional near_home state.

        No automatic transition is performed. A near_home state imported from
        the legacy reference has unknown age until its next real transition.
        """
        rt = self.runtime[person]
        if rt.state != State.NEAR_HOME or rt.near_home_entered_at is None:
            return None
        timestamp = _aware_utc(now if now is not None else self._clock())
        return max(0.0, (timestamp - rt.near_home_entered_at).total_seconds())

    def pending_near_home(
        self, *, min_seconds: float, now: datetime | None = None
    ) -> list[str]:
        """Return observed, prolonged provisional states (diagnostic only)."""
        if min_seconds < 0:
            raise ValueError("Minimum seconds must not be negative")
        return [
            person
            for person in self.people
            if (
                (age := self.near_home_age_seconds(person, now=now)) is not None
                and age >= min_seconds
            )
        ]

    def all_away(self) -> bool | None:
        """Conservative internal verdict: stale restored states never prove absence.

        A confirmed HOME or NEAR_HOME means not all away. An absent member
        snapshot or unknown state means we cannot establish certainty. Only
        when every member has a non-restored AWAY state is the verdict True.
        This is still an internal shadow calculation, not an HA entity.
        """
        runtimes = tuple(self.runtime.values())
        if not runtimes:
            return None
        if any(
            rt.state in (State.HOME, State.NEAR_HOME)
            and not rt.restored_from_storage
            for rt in runtimes
        ):
            return False
        if any(rt.state is None or rt.restored_from_storage for rt in runtimes):
            return None
        return True
