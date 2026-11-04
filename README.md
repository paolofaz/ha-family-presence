# Family Presence — Home Assistant

An independent, configurable, multi-person presence finite-state machine (FSM).
Sources: phone tracker, Watch BLE, optional bag BLE sensor and shared
gate/door/lock/alarm evidence. The original private family YAML is **not**
included in this repository.

> **RC1 development branch (0.1.0rc1): NOT RELEASED; shadow-only until approved.** Do not disable the existing
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
- `recent_events` contains up to twelve accepted/ignored decisions per person,
  including event, outcome, timestamp, state and reason. It is persisted and
  used only for diagnostics.
- `comparison_status` is `aligned`, `diverged`, `unknown` or
  `not_configured`; `divergence_since` records the current continuous
  mismatch, with no alerts or alarm actions.

### Alpha 8: authoritative all-away aggregate, including manual force

The aggregate **Casa certamente vuota** follows exactly the original YAML
definition: it is **ON iff every configured member's FSM state is AWAY**.
A manually forced AWAY is an authoritative AWAY, not a request for new proof.
A restored AWAY also counts. Any HOME, NEAR_HOME or unknown state makes it
OFF. The aggregate is False when there are no configured people.

The new `binary_sensor` **Family Presence Shadow - Casa certamente vuota**
shows these ON/OFF transitions immediately, including manual button presses,
and remains a diagnostic shadow entity separate from the original
`binary_sensor.casa_certamente_vuota` controlled by YAML. The diagnostic
`Family Presence Shadow - Diagnostica casa` sensor explains which state
determines the result. Contradicting iPhone/Watch readings appear only as
`source_warnings`, **never as a veto to a manual decision**.

**Do not point alarm/lock/heating automations at the new shadow binary sensor.**
A separate cutover will be needed after field comparison, when only one FSM
will be allowed to drive production presence outputs.

### Alpha 9: automatic parity with the legacy YAML helpers

The shadow home-empty binary sensor now compares itself with the aggregate
**reconstructed from the explicitly mapped legacy `input_select` references**
for every person. It does **not** read or modify the live
`binary_sensor.casa_certamente_vuota` entity. This is possible because the
old template is ON if and only if every old person helper is `away`.

The new attributes `legacy_comparison_status`,
`legacy_expected_all_away`, `aggregate_matches_legacy`,
`legacy_differing_members`, `legacy_divergence_since`, and
`legacy_missing_reference_members`/`legacy_unavailable_reference_members`
make mismatches actionable. Comparison statuses distinguish `aligned`,
`aggregate_divergence`, `member_divergence`, `not_configured` and
`reference_unavailable`. The timer tracks continuous mismatch during the
current integration runtime. Missing or unavailable YAML references never
produce a fake comparison result.

This comparison is strictly **diagnostic**. FSM transitions and the
authoritative **all members away = on**, including force buttons, are
unchanged.

### Beta 1: direct parity with live YAML empty-home binary

Optional configuration in **Reconfigure → Shared household sensors**:
map the legacy `binary_sensor.casa_certamente_vuota`. The beta observes
the **actual** YAML binary in addition to rebuilding its expected result from
all mapped legacy person helpers. New read-only attributes:
`actual_legacy_state`, `actual_legacy_all_away`,
`actual_legacy_matches_expected` and
`actual_legacy_matches_shadow`. This helps distinguish a difference in
the two FSMs from delayed or unavailable YAML-template updates. Mapping is
optional; neither the old template nor the old member helpers are ever written.

The exact `all members away = on` rule, including manual overrides, is
unchanged. All integration outputs remain **shadow**. Use the
[Italian Beta 1 field test](docs/beta1-field-test.md) for every family member
before attempting any final cutover.

### RC1 opt-in output profile — code under development, no cutover yet

The RC1 branch prepares future definitive names in `presentation.py`
without changing **any existing entity unique ID**. With no explicit activation all
entities keep their Beta 1 Shadow labels and diagnostic categories.
Changing display names alone does not necessarily change the entity IDs
Home Assistant has already stored. The YAML cutover must review the
entity registry and retire the old `casa_certamente_vuota` entity before
claiming that ID for a new one.

`activation_contract.py` codifies the existing YAML rules for arming,
disarming and unlocked-door warnings as **pure testable functions**;
it is never invoked as a Home Assistant service call.
The physical-event YAML automation `presenza_evento_fisico` is
also a state writer and must be deactivated or split in the final cutover.

The RC1 code now provides a guarded Configure → Activation options step:
registry-backed output preflight and typed ATTIVA/OMBRA confirmations.
It changes the output presentation/metadata only; it never rewires YAML,
claims entity IDs or performs actuator calls. It starts in Shadow and is
**not** an approved production migration. See
[operational runbook](docs/rc1-operational-runbook-it.md) and
[generic YAML consumer example](docs/rc1-yaml-consumers.example.yaml).

The migration is not yet active; the legacy YAML continues all real actions.
See [RC1 cutover checklist](docs/cutover-plan-it.md),
[RC1 project handoff](docs/rc1-project-handoff.md) and
[Italian dashboard time format](docs/rc1-dashboard-local-time.md).

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
2. Install the Beta 1 (v0.1.0b1) prerelease via HACS; restart Home Assistant.
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
   `ignored_event_count`, `recent_events`, backpack schedule fields and `manual_last_action`.
   **Never use shadow entities to control the alarm.**

For more detail, enable INFO logs under
`custom_components.family_presence`. All FSM decisions are calculated and
saved independently of the legacy YAML, and compatible snapshots are restored
after restart (marked `restored_from_storage`). Shared physical-event
timestamps are not restored. A stored AWAY remains authoritative for the exact state-based all-away
aggregate, while its restored provenance stays visible in diagnostics.

## Safety / what's next

No production presence entities, no production `casa_certamente_vuota` output, no
actuator calls and no automatic migration of alarm automations. Field-test the
schedule boundaries, delayed BLE, overnight time windows, manual buttons, event
races, restart and all-away confidence before enabling any new production
output. A manual **Forza fuori casa** may eventually contribute to arming when
real outputs exist; that workflow requires separate approval and testing.

See [Architecture](docs/architecture.md), [Backpack transitions](docs/bag-policy.md),
[Alpha 6 field test](docs/alpha6-reliability.md),\n[Alpha 7 history](docs/alpha7-household-safety.md),
[Alpha 8 authoritative aggregate](docs/alpha8-aggregate.md),
[Alpha 9 parity diagnostics](docs/alpha9-legacy-parity.md),
[Beta 1 complete field test](docs/beta1-field-test.md),
[Shadow test plan](docs/shadow-test-plan.md) and
[GitHub PR #1](https://github.com/paolofaz/ha-family-presence/pull/1).

The FSM and its conditions live in Python. BLE scanning stays in the
independent Watch/Beacon providers; actions (alarm, heating, notifications)
remain in standalone Home Assistant automations. License: MIT.
