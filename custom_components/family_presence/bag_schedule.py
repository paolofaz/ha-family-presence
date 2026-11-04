"""One event-driven backpack schedule per family member.

This module is independent of Home Assistant. A disabled bag contributes no
FSM events. Equal start/end mean all 24 hours; crossing midnight is supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

ALL_DAYS = (0, 1, 2, 3, 4, 5, 6)
SCHOOL_DAYS = (0, 1, 2, 3, 4)


def parse_clock(value: str) -> time:
    result = time.fromisoformat(value)
    if result.tzinfo is not None:
        raise ValueError("A local clock time without timezone is required")
    return result


@dataclass(frozen=True, slots=True)
class BagSchedule:
    enabled: bool = True
    start: str = "07:00"
    end: str = "09:10"
    days: tuple[int, ...] = SCHOOL_DAYS

    def __post_init__(self) -> None:
        parse_clock(self.start)
        parse_clock(self.end)
        if not isinstance(self.enabled, bool):
            raise ValueError("Enabled must be a boolean")
        if not all(isinstance(day, int) and 0 <= day <= 6 for day in self.days):
            raise ValueError("Weekdays must be integers 0–6")

    def includes(self, local_dt: datetime) -> bool:
        """Whether an ON→OFF occurring at this timestamp has exit priority."""
        if not self.enabled or not self.days:
            return False
        start, end = parse_clock(self.start), parse_clock(self.end)
        now = local_dt.timetz().replace(tzinfo=None)
        weekday = local_dt.weekday()
        if start == end:  # 00:00 → 00:00 or any equal time: 24h
            return weekday in self.days
        if start < end:
            return weekday in self.days and start <= now < end
        # Overnight window: Monday 22:00–02:00 includes Tuesday at 01:00.
        return (now >= start and weekday in self.days) or (
            now < end and (weekday - 1) % 7 in self.days
        )

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "start": self.start, "end": self.end, "days": list(self.days)}

    @classmethod
    def from_dict(cls, value: dict) -> "BagSchedule":
        return cls(
            enabled=value["enabled"],
            start=value["start"],
            end=value["end"],
            days=tuple(value["days"]),
        )


def legacy_schedule(policy: str | None) -> BagSchedule:
    """One-time migration of old two-policy config, not a runtime mode."""
    if policy == "always":
        return BagSchedule(True, "00:00", "00:00", ALL_DAYS)
    return BagSchedule()  # Previously "legacy": weekday school window.
