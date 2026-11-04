"""Read-only shadow-mode coordinator; no Home Assistant imports or writes."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Awaitable, Callable

from .fsm import BagPolicy, BagStatus, Decision, Event, Evidence, State, decide, recent_before
from .bag_schedule import BagSchedule


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
    bag_policy: BagPolicy = BagPolicy.ALWAYS  # Used only for old snapshot migration.
    bag_schedule: BagSchedule = BagSchedule()


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


@dataclass(frozen=True, slots=True)
class ShadowIgnored:
    person: str
    event: Event
    reason: str
    when: datetime
    reference: State | None


@dataclass(slots=True)
class PersonRuntime:
    state: State | None = None
    last_reason: str | None = None
    last_changed: datetime | None = None
    # Restored near_home has unknown age; only newly observed entries have a timer.
    near_home_entered_at: datetime | None = None
    restored_from_storage: bool = False
    # State and reason belong exclusively to the independent FSM.
    # The legacy YAML reference is never used to seed or reconcile runtime.
    state_origin: str = "unknown"
    reason_origin: str = "not_recorded"
    # True only after a BAG_LEFT that actually caused AWAY. This trip can
    # survive Watch -> NEAR_HOME and a validated snapshot, but no other exit.
    bag_return_eligible: bool = False
    # Manual forcing is a single event, not a hold or priority override.
    manual_last_action: str | None = None
    manual_last_action_at: datetime | None = None
    last_source_event_at: datetime | None = None
    last_blocked_event: Event | None = None
    last_blocked_at: datetime | None = None
    last_ignored_event: Event | None = None
    last_ignored_reason: str | None = None
    last_ignored_at: datetime | None = None
    ignored_count: int = 0
    recent_events: list[dict[str, str | None]] = field(default_factory=list)
    comparison_status: str = "unknown"
    divergence_since: datetime | None = None
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
        legacy_aggregate: str | None = None,
        local_timezone: tzinfo = timezone.utc,
        report: Callable[[ShadowDecision], None] | None = None,
        report_block: Callable[[ShadowBlocked], None] | None = None,
        report_ignore: Callable[[ShadowIgnored], None] | None = None,
    ) -> None:
        self.people = {p.key: p for p in people}
        if len(self.people) != len(people):
            raise ValueError("Person identifiers must be unique")
        # Never read a legacy input_select to initialize presence. State and
        # reason are owned by this FSM, not by the comparison baseline.
        self.runtime: dict[str, PersonRuntime] = {
            p.key: PersonRuntime() for p in people
        }
        self._physical: dict[str, datetime] = {}
        self._read = read_state
        self._clock = clock
        self._sleep = sleep
        self.windows = windows
        self.alarm = alarm
        self.legacy_aggregate = legacy_aggregate
        self.local_timezone = local_timezone
        self.report = report
        self.report_block = report_block
        self.report_ignore = report_ignore
        self._listeners: set[Callable[[str], None]] = set()
        # Since the current runtime started; this does not gate any FSM state.
        self.parity_status = "not_configured"
        self.parity_diverged_since: datetime | None = None
        self._refresh_parity_comparison()

    def legacy_comparison(self):
        """Read-only aggregation from explicitly mapped old YAML helpers."""
        from .comparison import compare_legacy

        return compare_legacy(self)

    def _refresh_parity_comparison(self) -> None:
        """Track the start of an uninterrupted, verifiable disagreement."""
        status = self.legacy_comparison().status
        mismatched = status in ("aggregate_divergence", "member_divergence")
        previously_mismatched = self.parity_status in (
            "aggregate_divergence", "member_divergence"
        )
        if mismatched and not previously_mismatched:
            self.parity_diverged_since = _aware_utc(self._clock())
        elif not mismatched:
            self.parity_diverged_since = None
        self.parity_status = status

    def async_add_listener(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Register local shadow updates for diagnostic entities and storage."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _notify(self, person: str) -> None:
        # Includes updates to mapped YAML references, not just FSM transitions.
        self._refresh_parity_comparison()
        for listener in tuple(self._listeners):
            listener(person)

    def notify_source_update(self, person: str) -> None:
        """Refresh comparison after a legacy/source entity has changed."""
        self._refresh_comparison(person)
        self._notify(person)

    def notify_legacy_aggregate_update(self) -> None:
        """Refresh external-template parity without touching the FSM."""
        if self.people:
            self._notify(next(iter(self.people)))
        else:
            self._refresh_parity_comparison()

    def _comparison_status(self, person: str) -> str:
        cfg = self.people[person]
        if not cfg.reference:
            return "not_configured"
        baseline = parse_state(self._read(cfg.reference))
        state = self.runtime[person].state
        if baseline is None or state is None:
            return "unknown"
        return "aligned" if baseline == state else "diverged"

    def _refresh_comparison(self, person: str) -> None:
        rt = self.runtime[person]
        status = self._comparison_status(person)
        if status == "diverged" and rt.comparison_status != "diverged":
            rt.divergence_since = _aware_utc(self._clock())
        elif status != "diverged":
            rt.divergence_since = None
        rt.comparison_status = status

    @staticmethod
    def _append_event(rt: PersonRuntime, event: Event, at: datetime,
                      outcome: str, reason: str) -> None:
        """Keep a small, scrubbed audit trail suitable for HA attributes."""
        rt.recent_events.append({
            "at": _aware_utc(at).isoformat(),
            "event": event.value,
            "outcome": outcome,
            "state": rt.state.value if rt.state is not None else None,
            "reason": reason,
        })
        if len(rt.recent_events) > 12:
            del rt.recent_events[:-12]

    def _record_ignored(self, person: str, event: Event, at: datetime, reason: str) -> None:
        """Record an intentionally ignored event without modifying presence."""
        rt = self.runtime[person]
        rt.last_ignored_event = event
        rt.last_ignored_reason = reason
        rt.last_ignored_at = _aware_utc(at)
        rt.ignored_count += 1
        self._append_event(rt, event, at, "ignored", reason)
        if self.report_ignore:
            cfg = self.people[person]
            self.report_ignore(ShadowIgnored(
                person, event, reason, rt.last_ignored_at,
                parse_state(self._read(cfg.reference)) if cfg.reference else None,
            ))
        self._notify(person)

    def note_ignored(self, person: str, event: Event, *, at: datetime, reason: str) -> None:
        """Record a rejected source transition (including invalid recovery)."""
        self._record_ignored(person, event, at, reason)

    @staticmethod
    def _source_fingerprint(person: PersonSources) -> str:
        """Stable across schedule edits; changes if a physical source is remapped."""
        mapping = {
            "iphone": person.iphone,
            "watch": person.watch,
            "bag": person.bag,
        }
        return hashlib.sha256(
            json.dumps(mapping, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _fingerprint(
        person: PersonSources, *, legacy: bool = False,
        old_format: bool = False,
    ) -> str:
        """New snapshots use source + schedule; legacy formats use old policy.

        The old YAML helper was part of the v1 fingerprint only. It never
        affects the current FSM and is only checked for format-1 migration.
        """
        mapping = {
            "iphone": person.iphone,
            "watch": person.watch,
            "bag": person.bag,
        }
        if legacy or old_format:
            mapping["bag_policy"] = person.bag_policy.value
            if legacy:
                mapping["reference"] = person.reference
        else:
            mapping["bag_schedule"] = person.bag_schedule.to_dict()
        return hashlib.sha256(
            json.dumps(mapping, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Serialize only shadow-owned state and diagnostic explanation."""
        return {
            "format": 5,
            "people": {
                key: {
                    "fingerprint": self._source_fingerprint(self.people[key]),
                    "state": rt.state.value if rt.state is not None else None,
                    "reason": rt.last_reason,
                    # Additive format-5 field: earlier RC5 snapshots default
                    # safely to False instead of trusting human-readable reasons.
                    "bag_return_eligible": rt.bag_return_eligible,
                    "last_changed": (
                        rt.last_changed.isoformat() if rt.last_changed else None
                    ),
                    "manual": {
                        "last_action": rt.manual_last_action,
                        "last_action_at": (
                            rt.manual_last_action_at.isoformat()
                            if rt.manual_last_action_at else None
                        ),
                    },
                    "ignored": {
                        "event": rt.last_ignored_event.value if rt.last_ignored_event else None,
                        "reason": rt.last_ignored_reason,
                        "at": rt.last_ignored_at.isoformat() if rt.last_ignored_at else None,
                        "count": rt.ignored_count,
                    },
                    "recent_events": list(rt.recent_events[-12:]),
                }
                for key, rt in self.runtime.items()
            },
        }

    def restore_snapshot(self, data: Any) -> int:
        """Recover FSM-owned state/reason regardless of the legacy YAML state.

        Legacy references are display-only. A saved AWAY counts as AWAY for
        the strict, user-defined all-away aggregate, while source provenance
        remains visible separately. Do not restore physical event timestamps
        or infer a near_home age. Version 1 snapshots are supported for upgrade.
        """
        if not isinstance(data, dict) or data.get("format") not in (1, 2, 3, 4, 5):
            return 0
        people = data.get("people")
        if not isinstance(people, dict):
            return 0
        legacy = data["format"] == 1
        restored = 0
        for key, rt in self.runtime.items():
            record = people.get(key)
            if not isinstance(record, dict):
                continue
            expected = (
                self._source_fingerprint(self.people[key])
                if data["format"] == 5 else
                self._fingerprint(
                    self.people[key], legacy=legacy, old_format=data["format"] in (2, 3)
                )
            )
            if record.get("fingerprint") != expected:
                continue
            saved_state = parse_state(record.get("state"))
            if saved_state is None:
                continue
            rt.state = saved_state
            rt.state_origin = "saved_shadow_unverified"
            rt.restored_from_storage = True
            rt.bag_return_eligible = (
                data["format"] == 5
                and record.get("bag_return_eligible") is True
                and saved_state in (State.AWAY, State.NEAR_HOME)
                and bool(self.people[key].bag)
            )

            reason = record.get("reason")
            if isinstance(reason, str) and reason.strip():
                rt.last_reason = reason
                rt.reason_origin = "saved_snapshot_unverified"
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

            manual = record.get("manual") if data["format"] in (4, 5) else None
            if isinstance(manual, dict):
                action = manual.get("last_action")
                rt.manual_last_action = action if isinstance(action, str) else None
                ts = manual.get("last_action_at")
                if isinstance(ts, str):
                    try:
                        rt.manual_last_action_at = _aware_utc(
                            datetime.fromisoformat(ts)
                        )
                    except ValueError:
                        pass
            if data["format"] == 5 and isinstance(record.get("ignored"), dict):
                ignored = record["ignored"]
                try:
                    rt.last_ignored_event = Event(ignored.get("event"))
                except (TypeError, ValueError):
                    pass
                reason = ignored.get("reason")
                rt.last_ignored_reason = reason if isinstance(reason, str) else None
                try:
                    rt.last_ignored_at = _aware_utc(datetime.fromisoformat(ignored["at"]))
                except (KeyError, ValueError, TypeError):
                    pass
                count = ignored.get("count")
                if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                    rt.ignored_count = count
            if data["format"] == 5 and isinstance(record.get("recent_events"), list):
                # Ignore malformed history entries; never trust them for decisions.
                for item in record["recent_events"][-12:]:
                    if not isinstance(item, dict):
                        continue
                    event_name, outcome = item.get("event"), item.get("outcome")
                    at_value, reason = item.get("at"), item.get("reason")
                    state_value = item.get("state")
                    if (isinstance(event_name, str)
                            and event_name in Event._value2member_map_
                            and outcome in ("ignored", "applied")
                            and isinstance(at_value, str)
                            and isinstance(reason, str) and len(reason) <= 256
                            and state_value in ("home", "away", "near_home", None)):
                        rt.recent_events.append({
                            "at": at_value,
                            "event": event_name,
                            "outcome": outcome,
                            "state": state_value,
                            "reason": reason,
                        })
            self._refresh_comparison(key)
            restored += 1
        if restored:
            self._refresh_parity_comparison()
        return restored

    async def force_state(self, person: str, state: State) -> ShadowDecision:
        """One-off, explicit human event; future valid sensor events may win."""
        if state not in (State.HOME, State.AWAY):
            raise ValueError("Only HOME or AWAY can be forced")
        self.note_person_event(person)  # Invalidate any delayed Watch ON.
        decision = await self.process(
            person,
            Event.MANUAL_HOME if state == State.HOME else Event.MANUAL_AWAY,
            event_time=self._clock(),
        )
        assert decision is not None
        return decision

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
            bag_departure_active=config.bag_schedule.includes(
                reference.astimezone(self.local_timezone)
            ),
            bag_enabled=config.bag_schedule.enabled,
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
            if (
                rt.last_source_event_at is not None
                and event not in (Event.RECONCILE, Event.MANUAL_HOME, Event.MANUAL_AWAY)
                and at < rt.last_source_event_at
            ):
                # Older queued callbacks cannot override a newer event.
                self._record_ignored(person, event, at, "Evento accodato precedente a uno già elaborato")
                return None
            if (
                rt.manual_last_action_at is not None
                and event not in (Event.MANUAL_HOME, Event.MANUAL_AWAY)
                and at <= rt.manual_last_action_at
            ):
                # A delayed event from before a manual button press must not
                # undo the forced state; only events fired AFTER may do so.
                self._record_ignored(person, event, at, "Evento precedente alla correzione manuale")
                return None

            if event == Event.WATCH_SEEN:
                await self._sleep(self.windows.watch_on_delay_seconds)
                # Recheck both revision and live watch state after 2 seconds.
                if (revision is not None and revision != rt.source_revision) or (
                    not config.watch or self._read(config.watch) != "on"
                ):
                    self._record_ignored(person, event, at, "Rilevamento Watch superato o non più valido")
                    return None

            # OFF physical correlation must use last_seen_before_off, not the
            # notification receipt time. Missing last_seen = no physical match.
            if event == Event.WATCH_LOST and last_seen_before_off is not None:
                reference = _aware_utc(last_seen_before_off)
            elif event == Event.WATCH_LOST:
                reference = None
            elif event == Event.BAG_LEFT:
                # The schedule applies at the actual OFF event timestamp,
                # not at queue-processing time (could cross a boundary).
                reference = at
            else:
                reference = _aware_utc(self._clock())
            evidence = self._evidence(config, reference or at, kind=physical_kind)
            if reference is None and event == Event.WATCH_LOST:
                evidence = Evidence(
                    iphone_outside=evidence.iphone_outside,
                    alarm_armed_away=evidence.alarm_armed_away,
                    bag_status=evidence.bag_status,
                )

            # Bag transitions are real events, never a permanent OFF veto.
            # If its state has since changed, drop the delayed stale callback.
            if event == Event.BAG_LEFT and evidence.bag_status != BagStatus.ABSENT:
                self._record_ignored(person, event, at, "Zaino non più assente: evento obsoleto")
                return None
            if event == Event.BAG_ARRIVED and evidence.bag_status != BagStatus.PRESENT:
                self._record_ignored(person, event, at, "Zaino non più presente: evento obsoleto")
                return None

            if event not in (Event.RECONCILE, Event.MANUAL_HOME, Event.MANUAL_AWAY):
                rt.last_source_event_at = at
            result: Decision | None = decide(
                rt.state, event, evidence,
                bag_return_eligible=rt.bag_return_eligible,
            )

            # A real newer phone event can corroborate a manually forced or
            # restored value even when the FSM is already in that same state.
            # This affects provenance/confidence only; it does not manufacture
            # a new transition or change the per-person state.
            unverified = rt.restored_from_storage or rt.state_origin == "manual_force"
            # A fresh iPhone departure is more specific than the earlier bag
            # departure even if the state was already AWAY. Revoke the bag
            # right to return HOME and update the reason without a state flip.
            if (result is None and event == Event.IPHONE_LEFT
                    and rt.state == State.AWAY and rt.bag_return_eligible
                    and evidence.iphone_outside):
                result = Decision(State.AWAY, "iPhone left home zone")
            if result is None and unverified and config.iphone:
                if (event == Event.IPHONE_LEFT and rt.state == State.AWAY
                        and evidence.iphone_outside):
                    result = Decision(State.AWAY, "iPhone left home zone")
                elif (event == Event.IPHONE_ARRIVED and rt.state == State.HOME
                      and self._read(config.iphone) == "home"):
                    result = Decision(State.HOME, "iPhone entered home zone")
            if result is None:
                if event == Event.RECONCILE:
                    return None  # Boot/recovery must never fabricate a transition.
                if event in (Event.BAG_LEFT, Event.BAG_ARRIVED) and not evidence.bag_enabled:
                    reason = "Zaino disabilitato nella configurazione"
                elif event == Event.BAG_LEFT and not evidence.bag_departure_active:
                    reason = "Uscita zaino fuori dalla fascia oraria configurata"
                elif event == Event.BAG_LEFT and rt.state == State.AWAY:
                    reason = "Zaino uscito ma persona già fuori: causa di uscita invariata"
                elif event == Event.BAG_ARRIVED and rt.state == State.HOME:
                    reason = "Zaino rilevato, persona già in casa"
                elif event == Event.BAG_ARRIVED:
                    reason = "Zaino rilevato, ma non risulta una uscita causata dallo zaino"
                elif event == Event.WATCH_LOST:
                    reason = "Watch non rilevato, ma mancano condizioni di uscita valide"
                elif event == Event.WATCH_SEEN:
                    reason = "Watch rilevato, ma lo stato attuale non richiede un rientro"
                elif event == Event.PHYSICAL_ENTRY:
                    reason = "Evento fisico senza Watch e stato vicino casa compatibili"
                else:
                    reason = "Nessun cambio di presenza richiesto dallo stato attuale"
                self._record_ignored(person, event, at, reason)
                return None
            previous = rt.state
            rt.state = result.state
            if event == Event.BAG_LEFT:
                # Only a departure which actually establishes AWAY grants
                # this bag the right to confirm the next arrival.
                rt.bag_return_eligible = previous != State.AWAY
            elif not (event == Event.WATCH_SEEN and previous == State.AWAY
                      and result.state == State.NEAR_HOME):
                # Watch proximity is provisional; retain the known bag trip.
                # Other applied events, including manual AWAY, supersede it.
                rt.bag_return_eligible = False
            self._refresh_comparison(person)
            rt.last_reason = result.reason
            rt.restored_from_storage = False
            manual = event in (Event.MANUAL_HOME, Event.MANUAL_AWAY)
            rt.state_origin = "manual_force" if manual else "observed_transition"
            rt.reason_origin = "manual_force" if manual else "observed_event"
            when = _aware_utc(self._clock())
            if manual:
                rt.manual_last_action = event.value
                rt.manual_last_action_at = when
            near_home_duration: float | None = None
            if result.state != previous or manual:
                rt.last_changed = when
                if previous == State.NEAR_HOME:
                    if rt.near_home_entered_at is not None:
                        near_home_duration = max(
                            0.0, (when - rt.near_home_entered_at).total_seconds()
                        )
                    rt.near_home_entered_at = None
                if result.state == State.NEAR_HOME:
                    rt.near_home_entered_at = when
            self._append_event(rt, event, at, "applied", result.reason)
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

    def household_assessment(self):
        """Compute a diagnostics-only readiness report without side effects."""
        from .readiness import assess_household

        return assess_household(self)

    def all_away(self) -> bool:
        """Exactly the legacy rule: all configured people must be AWAY.

        Manual and restored states count like any other valid FSM state.
        Unknown/NEAR_HOME/HOME (or zero configured people) yield False.
        Source disagreement belongs to diagnostics, never to this decision.
        """
        return bool(self.people) and all(
            rt.state == State.AWAY for rt in self.runtime.values()
        )
