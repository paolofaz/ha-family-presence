"""Home Assistant bootstrap: foundation phase, intentionally no active listeners.

The original YAML automations MUST remain active until shadow-mode parity
and migration have been verified. No alarm or presence state is written here.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Accept stored configuration without activating an incomplete FSM."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the entry."""
    return True
