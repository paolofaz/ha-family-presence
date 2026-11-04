"""One stable virtual Home Assistant device for the entire household.

The individual sensors are separate entities, but every entity is attached to
the same virtual household device. This exposes no physical actuator.
"""
from __future__ import annotations

from .const import DOMAIN


def household_device_info(entry_id: str) -> dict:
    """Stable across configuration edits, restarts and display-name changes."""
    return {
        "identifiers": {(DOMAIN, f"{entry_id}_household")},
        "name": "Casa",
        "manufacturer": "Family Presence",
        "model": "FSM familiare",
    }
