# Family Presence architecture: shadow phase

## Installed modules

```text
Home Assistant (configured person + shared sensors)
     ↓
sources.py (valid state-change events only; physical-event timestamps)
     ↓
coordinator.py (per-person async lock; 2s Watch ON delay; current evidence)
     ↓
fsm.py (pure decision rules; confirmed absent bag always wins)
     ↓
in-memory shadow state + logs only (NO production entity writes)
```

Independent YAML automations continue controlling alarm, heating, warnings and notifications.

## BLE provider contracts

Family Presence consumes **standard Home Assistant entities** produced by independent BLE integrations. Neither raw iBeacon identity (UUID/Major/Minor) nor Watch IRKs belong in the FSM. The provider already applies configured 180-second absence timeouts; do **not** stack another mandatory 180-second bag absence delay in the FSM. See [ble-sources.md](ble-sources.md) for reviewed code, startup semantics, polling intervals and the ~180s period before a physically departed bag becomes OFF.

## Source and transition contracts

- Phone leaving `home` → `away`, phone returning `home` → `home`; invalid transitions are ignored.
- Watch ON is evaluated after a 2-second delay, and **discarded if Watch has since turned off or another phone/Watch/bag event has superseded it**. Watch ON while `away` enters `home` with gate/door/unlock corroboration in 120s, otherwise `near_home`.
- Watch OFF while `home` requires phone outside, gate/door closure/lock evidence relative to `last_seen_before_off`, or alarm armed away. Exit windows: gate 120s; door close and lock 90s.
- While `near_home`, physical gate/door opening/unlock + Watch ON confirms `home`.
- Bag OFF (strict mode) is a persistent veto: `away`, independent of time and competing sources. **A bag currently ON only removes the veto; its transition from OFF to ON sets `home`.** Legacy bag mode retains weekday 07:00–09:10 departure and no veto.
- A shared gate event **never identifies** which person used it; it only corroborates another person's sensor.
- Bag `unknown`/`unavailable` is not equivalent to OFF. Invalid/restore-only state changes are ignored; a recovering bag already OFF may trigger an absence reconciliation.
- Physical history is *not* reloaded on restarts; stored old gate evidence must never imply a new entry.

## Configuration and diagnostics

One household configuration entry, an arbitrary number of people, optional per-person reference `input_select`, phone/watch/bag entities, bag priority and household physical sources. Time windows live in options and follow the legacy defaults.

The read-only shadow state is initialized from the reference helper **once** at setup and is never written back. If no helper is mapped and no decisive input arrives, state remains unknown. Every shadow decision logs its reason and the *current* reference-helper state. `[shadow][blocked]` logs entry hypotheses vetoed by absent bag.

The in-memory `all_away()` returns unknown if any member is uninitialized. **There is no all-away binary sensor or HA presence entity yet.** Users must not migrate any YAML action to the new shadow engine.

## Provisional near-home state

`near_home` represents a pending Watch-based arrival without sufficient physical corroboration, not confirmed occupancy. The engine now measures the duration of observed provisional states; it **never expires them automatically**. The current all-away semantics remain conservative: one near-home member blocks `all_away=true`, while only `home` can trigger the independent return-alarm action. See [near-home.md](near-home.md).

## Safety limitations and upcoming tasks

- Source-event ordering has initial per-person serialization and revision checks, but needs HA integration tests for rapid races, setup/teardown, source restores and concurrency.
- Measure false bag OFF rates under the upstream 180s timeout and define an explicit, auditable manual override for a child returning without their bag, before live alarm migration.
- Build persistent internal state, stable person IDs, editable source mappings and fully translated diagnostic entities.
- Build actual time-aligned parity comparisons with the original YAML. A snapshot in the log is not proof of parity.
- Add a conservative all-away binary sensor **only after** reboot/unavailable behavior has been reviewed. The all-away output must not arm the alarm on uncertain states.
- Test first in shadow mode against the existing package, then migrate selected outputs and finally independent YAML automations, deliberately and reversibly.
- HACS topics, branding assets and release automation remain unfinished.

`async_unload_entry` removes listeners and cancels pending Watch ON tasks. An HA event adapter is now present but still experimental, not production-validated.
