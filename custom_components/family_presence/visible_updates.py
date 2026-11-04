"""Emit Home Assistant updates only when visible state or attributes change.

The FSM reports ignored BLE events and diagnostic updates to listeners. Such
events must not cause redundant writes for production presence entities.
"""
from __future__ import annotations

from typing import Any


def capture_visible_state(entity: Any, value: object) -> tuple[object, dict]:
    """Capture a representation independent of internal event counters."""
    return value, entity.extra_state_attributes


def async_write_if_visible_changed(entity: Any, value: object) -> bool:
    """Return True only when a meaningful change was published."""
    visible = capture_visible_state(entity, value)
    if visible == getattr(entity, "_last_visible_state", None):
        return False
    entity._last_visible_state = visible
    entity.async_write_ha_state()
    return True
