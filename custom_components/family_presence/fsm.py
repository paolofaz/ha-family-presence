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
    school_bag_window: bool = False
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
    bag_policy: BagPolicy = BagPolicy.ALWAYS,
) -> Decision | None:
    """Decide atomically. Confirmed bag absence wins before every other rule.

    ALWAYS: with the bag sensor currently OFF, force AWAY and suppress all
    conflicting input events until the bag is ON again. The caller must
    normalize OFF/ON/unknown/unavailable and serialize decisions per person.
    LEGACY: original morning-only bag departure, with no persistent veto.
    """
    if bag_policy == BagPolicy.ALWAYS and evidence.bag_status == BagStatus.ABSENT:
        return Decision(State.AWAY, "Bag absent (priority)") if current != State.AWAY else None

    if event == Event.RECONCILE:
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

    # Existing YAML updates reason even if already in the resulting state.
    if event == Event.BAG_ARRIVED:
        return Decision(State.HOME, "Bag arrived")
    if event == Event.BAG_LEFT and evidence.school_bag_window:
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
