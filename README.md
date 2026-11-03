# Family Presence — Home Assistant

An independent, configurable, multi-person presence finite-state machine (FSM).
Sources: phone tracker, Watch BLE, optional bag BLE sensor and shared
gate/door/lock/alarm evidence. The original private family YAML is **not**
included in this repository.

> **Experimental Alpha 6 (0.1.0a6), shadow-only.** Do not disable the existing
> YAML presence, alarm, heating or notification automations. Diagnostic states
> and manual buttons here do not write the original YAML helpers or operate
> alarms, heating or locks.

## What the FSM computes

- Each member independently has `home`, `near_home` or `away`.
- An iPhone tracker leaving/entering home establishes AWAY/HOME.
- Watch OFF uses iPhone outside or recent entrance evidence **relative to
  `last_seen_before_off`**. Watch ON waits 2 seconds, then requires physical
  corroboration to claim HOME; otherwise it can enter provisional NEAR_HOME.
- `near_home` has no automatic expiry, and prevents the internal certain-empty
  result from becoming true.
- Bag OFF and Watch OFF use the timeout already implemented by their separate
  BLE providers (currently 180s configured upstream); this integration adds no
  mandatory extra BLE timeout.

### Event-based backpack schedule (introduced in Alpha 5)

There are **no user-facing legacy/always bag policies**. Instead, each member
with a bag can configure **enabled**, **start time**, **end time**, and
**weekdays** in the Family Presence **Configure → Backpack schedule** menu.

- A genuine bag **ON→OFF**, within the configured departure window, sets AWAY.
  This is a transition event, **not a persistent veto**: a later valid phone or
  Watch/entrance event can change the state.
- Bag **OFF→ON** sets HOME at any hour, provided the bag is enabled.
- Disabled bag means **neither transition affects the FSM**.
- Start = end (e.g. **00:00–00:00**) means 24 hours on the selected weekdays.
  Overnight windows such as 22:00–02:00 are supported, including the next day.
- `unknown`/`unavailable` recovering to ON/OFF is not a physical
  arrival/departure. Restart with bag already OFF does not invent an exit.
- Existing Alpha 1–4 `always` settings migrate into **24h / all days**;
  previous `legacy` migrates into **Mon–Fri 07:00–09:10**. These are *schedule
  defaults*, not retained precedence modes. New members default to the school
  schedule and can change it.

### Alpha 6: robust restore and event diagnostics

- Stored states use **snapshot format 5**, fingerprinting only the person's
  input source mappings (iPhone/Watch/bag). Changing only backpack departure
  hours, days or enabled flag no longer discards an established shadow state.
- On upgrading from Alpha 5, an unchanged configuration is migrated immediately
  from format 4 to format 5. If a source is remapped, the old state is rejected.
  Format 4 cannot safely restore after an arbitrary schedule edit performed
  before that first successful Alpha 6 startup.
- Every ignored event is recorded with an Italian reason, timestamp and count;
  examples: bag departure outside schedule, disabled bag, stale queued callback
  or Watch exit without corroboration. Recovery from unknown/unavailable bag
  is diagnostic only, never a fabricated arrival.
- `comparison_status` is `aligned`, `diverged`, `unknown` or
  `not_configured`; `divergence_since` records the current continuous
  mismatch, with no alerts or alarm actions.

### Manual state forcing: one-off, not a hold

For **each person**, two **diagnostic buttons** appear:

- **Forza a casa**: immediately sets shadow HOME.
- **Forza fuori casa**: immediately sets shadow AWAY.

Neither button establishes any lasting priority. The **next new, valid sensor
event** is processed normally and may change the person again, regardless of
whether their bag remains OFF. Older queued events with timestamps preceding the
button press cannot undo it. The action and time are logged and stored with the
independent shadow state. These buttons do **not** control the alarm or YAML.

## Setup and diagnostics

1. Leave the original YAML package and all related automations running.
2. Install the Alpha 6 prerelease from the development branch when tagged and
   available through HACS; restart Home Assistant.
3. Add **Family Presence** under Settings → Devices & Services, and map your
   phone, Watch, optional bag, gate, door, lock and armed-away alarm entities.
4. Optionally map the original YAML `input_select` for **comparison only**.
   The new FSM never seeds or decides from the old helper.
5. Under **Configure**, change the six timestamp correlation windows or choose
   each person's backpack schedule. Under **Reconfigure**, edit source mappings,
   add/remove people or rename them while keeping stable IDs.
6. Inspect `sensor.family_presence_shadow_...` for `reason`,
   `state_origin`, `reason_origin`, `last_transition`, `legacy_state`,
   `matches_legacy`, `comparison_status`, `divergence_since`,
   `last_ignored_event`, `last_ignored_reason`, `last_ignored_at`,
   `ignored_event_count`, backpack schedule fields and `manual_last_action`.
   **Never use shadow entities to control the alarm.**

For more detail, enable INFO logs under
`custom_components.family_presence`. All FSM decisions are calculated and
saved independently of the legacy YAML, and compatible snapshots are restored
after restart (marked `restored_from_storage`). Shared physical-event
timestamps are not restored. A stored AWAY is not automatically trusted as
certain absence.

## Safety / what's next

No production presence entities, no HA `casa_certamente_vuota` output, no
actuator calls and no automatic migration of alarm automations. Field-test the
schedule boundaries, delayed BLE, overnight time windows, manual buttons, event
races, restart and all-away confidence before enabling any new production
output. A manual **Forza fuori casa** may eventually contribute to arming when
real outputs exist; that workflow requires separate approval and testing.

See [Architecture](docs/architecture.md), [Backpack transitions](docs/bag-policy.md),
[Alpha 6 field test](docs/alpha5-event-controls.md),
[Shadow test plan](docs/shadow-test-plan.md) and
[GitHub PR #1](https://github.com/paolofaz/ha-family-presence/pull/1).

The FSM and its conditions live in Python. BLE scanning stays in the
independent Watch/Beacon providers; actions (alarm, heating, notifications)
remain in standalone Home Assistant automations. License: MIT.
