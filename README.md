# Family Presence for Home Assistant

A configurable, multi-person Home Assistant presence FSM using phone zone tracking, BLE wearables, physical gate/door/lock events, and optional bag sensors.

> **Experimental shadow build (0.1.0a1): DO NOT REPLACE YOUR EXISTING YAML.** The integration now subscribes to HA inputs and computes **in-memory shadow decisions only**. It does **not** register production sensor entities, modify legacy `input_select` values, persist its internal FSM, or control alarm/locks/heating. It has not yet been end-to-end tested inside a running Home Assistant instance.

## Core behavior

- Per-person state `home` / `near_home` / `away`, with no fixed family size.
- Each person can map a phone tracker, Watch BLE sensor, optional bag sensor, a **legacy `input_select` reference** (for shadow comparison), and a bag priority policy.
- Shared gate switches/sensors, door contact, door lock and alarm are selectable.
- Event windows default to legacy values: Watch OFF: gate 120s, door/lock 90s relative to Watch `last_seen_before_off`; Watch ON: gate/door/unlock 120s, evaluated **after two seconds**.
- Bag policy `always`: a **currently OFF** bag forces `away` regardless of iPhone/Watch/door/gate. **OFF → ON** is a `home` event. With bag already ON, other sensors govern the FSM normally: bag presence does **not** permanently lock `home`.
- Bag policy `legacy`: the earlier behavior, with bag OFF causing departure only during the weekday 07:00–09:10 window; no precedence veto.
- `unknown` / `unavailable` is not OFF. Startup recovery does not invent arrival/departure transitions.
- `all_away()` is calculated internally, returning unknown if any person's state is unknown; there is intentionally **no live all-away entity yet**.

## Shadow setup (for safe testing)

1. Leave the original YAML package and all alarm/heating automations enabled.
2. Install the contents of `custom_components/family_presence/` under your HA `config/custom_components/family_presence/`. **This branch is experimental, not a release.**
3. Restart Home Assistant and add **Family Presence** under Settings → Devices & Services. Map the physical inputs and people.
4. For each existing person, select the corresponding `input_select.presenza_...` helper as **Legacy YAML presence helper**. It seeds the shadow FSM once on startup and is read for diagnostic comparisons; never written.
5. To see decisions and blocked false arrivals, enable info logs:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.family_presence: info
   ```

6. Review log entries `[shadow]` and `[shadow][blocked]`. They are **observations**, not state changes. No alarm automations should be switched over to this integration.

Without a legacy helper, a shadow person may begin **unknown** until a decisive event is observed. On every restart, shadow state is re-seeded from the legacy helper if mapped, then the current bag OFF constraint is reconciled. Internal event history is intentionally reset at restart.

**Limitations:** log lines include an instantaneous legacy-state snapshot, not a synchronized/eventually-consistent parity report. HA event-adapter behavior and reconfiguration are not yet fully tested in Home Assistant. Entity edits currently require rebuilding the config entry. Bag debounce, persistent state, manual override, diagnostics entities, and all-away sensor are not implemented.

## Files

- `custom_components/family_presence/fsm.py`: pure transition rules.
- `custom_components/family_presence/coordinator.py`: per-person serialized shadow decisions, timestamp evidence, revision control.
- `custom_components/family_presence/sources.py`: HA source subscriptions and normalization.
- `custom_components/family_presence/config_flow.py`: household/person mapping and options.
- `docs/baseline.md`: original YAML behavior.
- `docs/bag-policy.md`: bag precedence design and safety risks.
- `docs/near-home.md`: rationale for preserving provisional near_home, alarm implications, and shadow diagnostics.
- `docs/architecture.md`: architecture, transition semantics and migration roadmap.
- `tests/`: pure unit tests; run `python -m unittest discover -s tests -v`.
- `.github/workflows/validate.yml`: unit tests, hassfest and HACS validation.

The private household-specific YAML is intentionally **not included** in this public repository. License: MIT.

HACS packaging layout is prepared, but a passing HACS validation, approved branding, and an actual release are still future work.
