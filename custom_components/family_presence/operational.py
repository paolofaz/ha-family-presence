"""RC1 output-profile preflight; pure logic, no HA actuator calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .const import CONF_OUTPUT_PROFILE
from .presentation import FINAL, SHADOW, aggregate_presentation, person_presentation


def profile_from_options(options: Mapping[str, object]) -> str:
    """RC2 always exposes Final outputs; old RC1 options cannot override it."""
    return FINAL


@dataclass(frozen=True, slots=True)
class RegisteredOutput:
    entity_id: str | None
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class OutputAudit:
    """Registry readiness only: cannot establish the status of external YAML."""

    aggregate_entity_id: str | None
    member_entity_ids: tuple[tuple[str, str | None], ...]
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers


def audit_registry(
    entry_id: str,
    people: Sequence[tuple[str, str]],
    lookup: Callable[[str, str], RegisteredOutput],
    *,
    legacy_aggregate: str | None = None,
) -> OutputAudit:
    """Check registered unique IDs, never guess/change real entity IDs."""
    blockers: list[str] = []
    member_ids: list[tuple[str, str | None]] = []
    if not entry_id or not people:
        blockers.append("missing_household")

    for key, name in people:
        unique_id = person_presentation(entry_id, key, name).unique_id
        found = lookup("sensor", unique_id)
        member_ids.append((key, found.entity_id))
        if not found.entity_id:
            blockers.append(f"member_unregistered:{key}")
        elif found.disabled:
            blockers.append(f"member_disabled:{key}")

    aggregate = lookup(
        "binary_sensor", aggregate_presentation(entry_id).unique_id
    )
    if not aggregate.entity_id:
        blockers.append("aggregate_unregistered")
    elif aggregate.disabled:
        blockers.append("aggregate_disabled")
    if legacy_aggregate and aggregate.entity_id == legacy_aggregate:
        blockers.append("aggregate_is_legacy_reference")

    ids = [value for _, value in member_ids if value]
    if aggregate.entity_id:
        ids.append(aggregate.entity_id)
    if len(ids) != len(set(ids)):
        blockers.append("duplicate_output_entity_id")
    return OutputAudit(aggregate.entity_id, tuple(member_ids), tuple(blockers))
