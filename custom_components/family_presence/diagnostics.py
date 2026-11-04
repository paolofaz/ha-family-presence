"""Home Assistant integration diagnostics (downloaded on demand).

The output intentionally omits configuration data, person names, source entity
IDs, exact device_tracker zones, and BLE identifiers. No new HA entities are
created for debugging and Recorder remains unaffected.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .diagnostic_data import build_diagnostics

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry,
) -> dict[str, Any]:
    """Return a bounded, anonymized diagnostic report for the config entry."""
    runtime = entry.runtime_data
    return build_diagnostics(runtime.engine, runtime.access_history)
