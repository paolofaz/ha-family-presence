"""Pure FSM decision rules transcribed from the existing YAML behavior.

No Home Assistant imports, entities or side effects. The future event adapter
must validate input transitions and calculate time-window evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum


class State(StrEnum):
    HOME = "home"
    NEAR_HOME = "near_home"
    AWAY = "away"


class Event(StrEnum):
    IPHONE_LEFT = "iphone_left_home"
    IPHONE_ARRIVED = "iphone_entered_home"
    WATCH_LOST = "watch_off"
    WATCH_SEEN = "watch_on"
    PHYSICAL_ENTRY = "physical_entry"
    BAG_ARRIVED = "bag_arrived"
    BAG_LEFT = "bag_left"
    RECONCILE = "reconcile"
    MANUAL_HOME = "manual_home"
    MANUAL_AWAY = "manual_away"


class BagStatus(StrEnum):
    """A temporarily unavailable sensor is not an absent bag."""
    NOT_CONFIGURED = "not_configured"
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class BagPolicy(StrEnum):
    """Per-person precedence policy."""
    ALWAYS = "always"
    LEGACY = "legacy"


@dataclass(frozen=True, slots=True)
class Evidence:
    """Preprocessed evidence. Exit timestamps are relative to Watch last_seen."""
    iphone_outside: bool = False
    gate_exit: bool = False
    door_closed_exit: bool = False
    lock_exit: bool = False
    alarm_armed_away: bool = False
    door_open_entry: bool = False
    door_unlock_entry: bool = False
    gate_entry: bool = False
    watch_detected: bool = False
    physical_event_label: str = "physical event"
    bag_departure_active: bool = False
    bag_enabled: bool = True
    school_bag_window: bool = False  # Compatibility only for old test fixtures
    bag_status: BagStatus = BagStatus.NOT_CONFIGURED


@dataclass(frozen=True, slots=True)
class Decision:
    """New state and diagnostic reason. The state might remain unchanged."""
    state: State
    reason: str


def decide(
    current: State,
    event: Event,
    evidence: Evidence = Evidence(),
    *,
    bag_policy: BagPolicy = BagPolicy.ALWAYS,  # Migration-only compatibility; ignored
    bag_return_eligible: bool = False,
) -> Decision | None:
    """Gate a backpack arrival on a verified backpack-caused absence.

    The coordinator tracks causal provenance independently of reason strings.
    A backpack-caused absence cannot be overturned by a Watch detected at
    home or by shared door/gate evidence while that trip is unresolved.
    A real iPhone HOME event or manual HOME still confirms a return without
    the bag. An unrelated/manual departure cannot be resolved by bag ON.
    """
    if event == Event.MANUAL_HOME:
        return Decision(State.HOME, "Forzato in casa manualmente")
    if event == Event.MANUAL_AWAY:
        return Decision(State.AWAY, "Forzato fuori casa manualmente")
    if event == Event.RECONCILE:
        return None

    # Causal provenance, not the current bag BLE reading, governs this
    # safeguard. A Watch left at home may switch ON while its owner is away.
    # Even a shared door event must not turn this into a false HOME.
    if (bag_return_eligible and current in (State.AWAY, State.NEAR_HOME)
            and event in (Event.WATCH_SEEN, Event.PHYSICAL_ENTRY)):
        return None

    if event == Event.IPHONE_LEFT:
        return Decision(State.AWAY, "iPhone left home zone") if current != State.AWAY else None
    if event == Event.IPHONE_ARRIVED:
        return Decision(State.HOME, "iPhone entered home zone") if current != State.HOME else None

    if event == Event.WATCH_LOST:
        if current == State.NEAR_HOME:
            return Decision(State.AWAY, "Watch no longer detected before arrival confirmed")
        if current != State.HOME:
            return None
        if evidence.iphone_outside:
            return Decision(State.AWAY, "iPhone outside")
        if evidence.gate_exit:
            return Decision(State.AWAY, "Watch OFF + recent gate before last_seen")
        if evidence.door_closed_exit:
            return Decision(State.AWAY, "Watch OFF + recent door close before last_seen")
        if evidence.lock_exit:
            return Decision(State.AWAY, "Watch OFF + recent lock before last_seen")
        if evidence.alarm_armed_away:
            return Decision(State.AWAY, "Watch OFF + alarm armed away")
        return None

    if event == Event.WATCH_SEEN:
        if current != State.AWAY:
            return None
        if evidence.door_open_entry:
            return Decision(State.HOME, "Watch detected + recent door opening")
        if evidence.door_unlock_entry:
            return Decision(State.HOME, "Watch detected + recent unlock")
        if evidence.gate_entry:
            return Decision(State.HOME, "Watch detected + recent gate")
        return Decision(State.NEAR_HOME, "Watch detected near home")

    if event == Event.PHYSICAL_ENTRY:
        if current == State.NEAR_HOME and evidence.watch_detected:
            return Decision(State.HOME, "Watch detected + " + evidence.physical_event_label)
        return None

    if (event == Event.BAG_ARRIVED and evidence.bag_enabled
            and bag_return_eligible and current in (State.AWAY, State.NEAR_HOME)):
        return Decision(State.HOME, "Bag arrived")
    # BAG_LEFT never steals the departure reason from an already-AWAY person.
    if (event == Event.BAG_LEFT and evidence.bag_enabled
            and evidence.bag_departure_active and current != State.AWAY):
        return Decision(State.AWAY, "Bag left")
    return None


def recent_before(reference: datetime, occurrence: datetime | None, seconds: int) -> bool:
    """An event must occur no later than reference and within seconds."""
    if occurrence is None or seconds < 0:
        return False
    elapsed = (reference - occurrence).total_seconds()
    return 0 <= elapsed <= seconds


def school_bag_window(local_now: datetime) -> bool:
    """Current behavior: weekdays, 07:00 inclusive until 09:10 exclusive."""
    t = local_now.timetz().replace(tzinfo=None)
    return local_now.weekday() < 5 and time(7, 0) <= t < time(9, 10)
