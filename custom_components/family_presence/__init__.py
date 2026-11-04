"""Family Presence: independent production FSM with stable entity identities.

This integration does not modify external YAML or command HA actuators.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .operational import profile_from_options
from .access_history import AccessHistory


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
    access_history: AccessHistory
    access_store: Store
    unsubscribe_access_save: object


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore persisted state and activate read-only presence output entities."""
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

    # Dedicated Store: restored access timestamps exist for display only, never
    # for the coordinator\u0027s fresh physical-event correlation windows.
    access_store = Store(hass, 1, f"family_presence_access_events.{entry.entry_id}")
    access_history = AccessHistory(entry.data)
    access_history.restore_snapshot(await access_store.async_load())
    unsubscribe_access_save = access_history.async_add_listener(
        lambda: access_store.async_delay_save(access_history.snapshot, 2)
    )

    unsubscribe_save = engine.async_add_persist_listener(
        lambda: store.async_delay_save(engine.snapshot, 2)
    )
    adapter = ShadowSourceAdapter(hass, entry.data, engine, access_history)
    entry.runtime_data = ShadowRuntime(
        engine, adapter, store, unsubscribe_save, profile_from_options(entry.options),
        access_history, access_store, unsubscribe_access_save,
    )
    try:
        adapter.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await adapter.async_stop()
        unsubscribe_save()
        unsubscribe_access_save()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove all listeners and persist both FSM state and access history."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime: ShadowRuntime = entry.runtime_data
    await runtime.adapter.async_stop()
    runtime.unsubscribe_save()
    runtime.unsubscribe_access_save()
    await runtime.store.async_save(runtime.engine.snapshot())
    await runtime.access_store.async_save(runtime.access_history.snapshot())
    return True
