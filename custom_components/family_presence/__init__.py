"""Family Presence: independent FSM, optional controlled output profile.

This integration does not modify external YAML or command HA actuators.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .operational import profile_from_options


if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
    from .coordinator import ShadowCoordinator
    from .sources import ShadowSourceAdapter


PLATFORMS = ("sensor", "button", "binary_sensor")


@dataclass(slots=True)
class ShadowRuntime:
    engine: ShadowCoordinator
    adapter: ShadowSourceAdapter
    store: Store
    unsubscribe_save: object
    profile: str


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore shadow state, subscribe events, expose diagnostic-only sensors."""
    from homeassistant.helpers.storage import Store
    from .sources import ShadowSourceAdapter, build_coordinator

    store = Store(hass, 1, f"family_presence_shadow.{entry.entry_id}")
    engine = build_coordinator(hass, entry)
    saved = await store.async_load()
    restored = engine.restore_snapshot(saved)
    # Convert legacy snapshots immediately, before any Configure/reload can
    # change the backpack schedule and invalidate its old combined fingerprint.
    if restored and isinstance(saved, dict) and saved.get("format") != 5:
        await store.async_save(engine.snapshot())
    await engine.reconcile()

    unsubscribe_save = engine.async_add_listener(
        lambda _person: store.async_delay_save(engine.snapshot, 2)
    )
    adapter = ShadowSourceAdapter(hass, entry.data, engine)
    entry.runtime_data = ShadowRuntime(
        engine, adapter, store, unsubscribe_save, profile_from_options(entry.options)
    )
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
