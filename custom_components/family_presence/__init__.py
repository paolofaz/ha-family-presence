"""Family Presence: experimental read-only shadow diagnostics.

Legacy YAML remains the only production writer. No alarm, lock or heating
service calls exist in this integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
    from .coordinator import ShadowCoordinator
    from .sources import ShadowSourceAdapter


PLATFORMS = ("sensor",)


@dataclass(slots=True)
class ShadowRuntime:
    engine: ShadowCoordinator
    adapter: ShadowSourceAdapter
    store: Store
    unsubscribe_save: object


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore shadow state, subscribe events, expose diagnostic-only sensors."""
    from homeassistant.helpers.storage import Store
    from .sources import ShadowSourceAdapter, build_coordinator

    store = Store(hass, 1, f"family_presence_shadow.{entry.entry_id}")
    engine = build_coordinator(hass, entry)
    engine.restore_snapshot(await store.async_load())
    await engine.reconcile()

    unsubscribe_save = engine.async_add_listener(
        lambda _person: store.async_delay_save(engine.snapshot, 2)
    )
    adapter = ShadowSourceAdapter(hass, entry.data, engine)
    entry.runtime_data = ShadowRuntime(engine, adapter, store, unsubscribe_save)
    try:
        adapter.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await adapter.async_stop()
        unsubscribe_save()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove diagnostic entities/listeners and preserve last shadow snapshot."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime: ShadowRuntime = entry.runtime_data
    await runtime.adapter.async_stop()
    runtime.unsubscribe_save()
    await runtime.store.async_save(runtime.engine.snapshot())
    return True
