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
shadow state + diagnostic sensor entities + .storage snapshot
          (NO production presence writes)
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

One household configuration entry, an arbitrary number of people, optional per-person reference `input_select`, phone/watch/bag entities, bag priority and household physical sources. Each newly created person receives an immutable random `person_id`, used for shadow runtime/entity identity independently of their editable display name. Entries created by older scaffolds fall back to the casefolded name until migrated. Time windows live in options and follow the legacy defaults. A per-person `bag_policies` override map in options uses the stable `person_id` (legacy entries use casefolded names). The effective `bag_policy` is resolved on each config-entry reload, without changing the original person data.

**The YAML helper is now a pure comparison source** (`legacy_state`/`matches_legacy`), not a seed or decision input. Freshly configured people without a valid saved snapshot start unknown until an actual source event or confirmed absent bag yields a state. On restart, the shadow FSM restores its **own** compatible snapshot, including state, reason and last-change time, even if the YAML helper disagrees. The fingerprint is based on phone, Watch, bag and policy, not the comparison helper. Older Alpha 1–3 snapshots (format 1) are migrated using their original fingerprint, then rewritten in format 2. A restored state is explicitly flagged `restored_from_storage` and cannot establish all-away; physical event history and near_home elapsed age are never restored. Every new decision logs its own reason in Italian and the current reference-helper state only for comparison. Shadow source/reference changes refresh diagnostic attributes but never cause a YAML-based transition. `state_origin` distinguishes an observed event from a potentially stale saved snapshot; `reason_origin` distinguishes a new explanation from a saved historical one.

The in-memory `all_away()` returns unknown if any member is uninitialized **or has only a restored, potentially stale shadow state**. A freshly observed `home` or `near_home` rules out all-away, but only non-restored states can establish confirmed all-away. **There is no all-away binary sensor or production HA presence entity yet.** There is one read-only `sensor.family_presence_shadow_...` per person, with `mode=shadow_only`, source information, last reason, last transition and comparison to the legacy helper. It is a diagnostic surface only. Users must not migrate any YAML action to it.

## Provisional near-home state

`near_home` represents a pending Watch-based arrival without sufficient physical corroboration, not confirmed occupancy. The engine now measures the duration of observed provisional states; it **never expires them automatically**. The current all-away semantics remain conservative: one near-home member blocks `all_away=true`, while only `home` can trigger the independent return-alarm action. See [near-home.md](near-home.md).

## Configuration boundary

The **Options** menu provides only two actions: edit the six physical-event correlation windows, or choose **Priorità assoluta** / **Fascia scolastica** for a person's bag (the stable stored codes remain `always`/`legacy`). OptionsFlowWithReload restarts the **shadow** runtime to apply the new settings. It preserves other options and the stable per-person IDs. An additional **Reconfigure** flow edits the household/shared sensors and allows changing, adding or removing members while preserving stable person IDs. It refuses duplicate person-specific sensor sources and refuses to remove the last member. BLE scan/presence timeouts remain with their BLE source integrations.

No arbitrary YAML/Jinja/Python conditions or generic rule editor will be supported. State transitions and invariant enforcement are tested Python behavior, not per-user scripts. See [configuration-policy.md](configuration-policy.md).

## Safety limitations and upcoming tasks

- Source-event ordering has initial per-person serialization and revision checks, but needs HA integration tests for rapid races, setup/teardown, source restores and concurrency.
- Measure false bag OFF rates under the upstream 180s timeout and define an explicit, auditable manual override for a child returning without their bag, before live alarm migration.
- Production-ready persistence, migration of all legacy name-based IDs and fully translated diagnostic entities. Source mapping reconfiguration is now implemented, but must be tested against a real HA config entry. The current shadow snapshot is scoped to unchanged source mapping and uses the HA Store helper; it is not a production persistence guarantee.
- Build actual time-aligned parity comparisons with the original YAML. A snapshot in the log is not proof of parity.
- Add a conservative all-away binary sensor **only after** reboot/unavailable behavior has been reviewed. The all-away output must not arm the alarm on uncertain states.
- Test first in shadow mode against the existing package, then migrate selected outputs and finally independent YAML automations, deliberately and reversibly.
- HACS topics, branding assets and release automation remain unfinished.

`async_unload_entry` removes listeners and cancels pending Watch ON tasks. An HA event adapter is now present but still experimental, not production-validated.
