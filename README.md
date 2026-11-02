# Family Presence for Home Assistant

A configurable, multi-person Home Assistant presence FSM using phone zone tracking, BLE wearables, physical gate/door/lock events, and optional bag sensors.

> **Experimental shadow build (0.1.0a1): DO NOT REPLACE YOUR EXISTING YAML.** The integration subscribes to HA inputs, records *shadow-only* state snapshots and exposes **diagnostic shadow sensors**, never production presence entities. It does **not** modify existing `input_select` values, or control alarm/locks/heating. It has not yet been end-to-end tested inside a running Home Assistant instance.

## Core behavior

- Per-person state `home` / `near_home` / `away`, with no fixed family size.
- Each person can map a phone tracker, Watch BLE sensor, optional bag sensor, a **legacy `input_select` reference** (for shadow comparison), and a bag priority policy.
- Shared gate switches/sensors, door contact, door lock and alarm are selectable.
- Event windows default to legacy values: Watch OFF: gate 120s, door/lock 90s relative to Watch `last_seen_before_off`; Watch ON: gate/door/unlock 120s, evaluated **after two seconds**.
- Bag policy `always`: a **currently OFF** bag forces `away` regardless of iPhone/Watch/door/gate. **OFF → ON** is a `home` event. With bag already ON, other sensors govern the FSM normally: bag presence does **not** permanently lock `home`.
- Bag policy `legacy`: the earlier behavior, with bag OFF causing departure only during the weekday 07:00–09:10 window; no precedence veto.
- `unknown` / `unavailable` is not OFF. Startup recovery does not invent arrival/departure transitions.
- `all_away()` is calculated internally, returning unknown if any person's state is unknown; **no all-away entity** is exposed and no shadow sensor should be used to arm/disarm alarms.

## Shadow setup (for safe testing)

1. Leave the original YAML package and all alarm/heating automations enabled.
2. Install the contents of `custom_components/family_presence/` under your HA `config/custom_components/family_presence/`. **This branch is experimental, not a release.**
3. Restart Home Assistant and add **Family Presence** under Settings → Devices & Services. Map the physical inputs and people.
4. For each existing person, select the corresponding `input_select.presenza_...` helper as **Legacy YAML presence helper**. It seeds the shadow FSM once on startup and is read for diagnostic comparisons; never written.
5. The experimental `sensor.family_presence_shadow_...` entities can display the simulated state, last transition/reason, bag-policy conflict and comparison with the corresponding YAML helper. They are marked as **diagnostic**, have `mode: shadow_only`, and **must never be used as automation triggers**.
6. To see decisions and blocked false arrivals, enable info logs:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.family_presence: info
   ```

7. Review log entries `[shadow]` and `[shadow][blocked]`. They are **observations**, not state changes. No alarm automations should be switched over to this integration.

On restart, the integration prefers a **currently valid YAML helper state**. If the helper is missing/unknown, a compatible saved shadow snapshot may be restored and is explicitly flagged `restored_from_storage`. A snapshot is accepted only for the **same per-person source mapping and bag policy**. If neither helper nor snapshot is available, state remains unknown until a decisive event. Only state/reason/last-change metadata are stored; **BLE event, gate and door timestamps are intentionally cleared at restart** to avoid accidental reused evidence. A valid bag OFF constraint is reconciled on startup.

**Limitations:** log lines and diagnostic sensor comparisons include instantaneous legacy-state snapshots, not a synchronized parity report. HA event-adapter and new diagnostic sensor platform need real-world integration testing. Entity edits currently require rebuilding the config entry. Additional bag debounce, manual override, full production presence entities and all-away output are **not implemented**. Persisted shadow states are diagnostic-only and can be stale.

## Files

- `custom_components/family_presence/fsm.py`: pure transition rules.
- `custom_components/family_presence/coordinator.py`: per-person serialized decisions, timestamp evidence, revisions, source fingerprinting and state snapshot export/restore.
- `custom_components/family_presence/sensor.py`: read-only simulated presence state and diagnostic attributes (not for automations).
- `custom_components/family_presence/sources.py`: HA source subscriptions and normalization.
- `custom_components/family_presence/config_flow.py`: household/person mapping and options.
- `docs/baseline.md`: original YAML behavior.
- `docs/bag-policy.md`: bag precedence design and safety risks.
- `docs/near-home.md`: rationale for preserving provisional near_home, alarm implications, and shadow diagnostics.
- `docs/ble-sources.md`: reviewed beacon/Watch providers, 180s timing contracts and why not to merge all three integrations.
- `docs/architecture.md`: architecture, transition semantics and migration roadmap.
- `tests/`: pure unit tests; run `python -m unittest discover -s tests -v`.
- `.github/workflows/validate.yml`: unit tests, hassfest and HACS validation.

The private household-specific YAML is intentionally **not included** in this public repository. License: MIT.

HACS packaging layout is prepared, but a passing HACS validation, approved branding, and an actual release are still future work.
