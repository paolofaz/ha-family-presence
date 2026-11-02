"""Read-only Family Presence shadow integration bootstrap.

The legacy YAML is the ONLY production state writer at this stage.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Track events in shadow memory only. Never change HA states or actuators."""
    # Lazy HA-only imports let pure FSM unit tests run without Home Assistant.
    from .sources import ShadowSourceAdapter, build_coordinator

    engine = build_coordinator(hass, entry)
    adapter = ShadowSourceAdapter(hass, entry.data, engine)
    adapter.start()
    entry.runtime_data = adapter
    await engine.reconcile()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unsubscribe source listeners and cancel pending Watch evaluations."""
    await entry.runtime_data.async_stop()
    return True
