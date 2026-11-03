> **Historical Alpha 7 design, superseded by Alpha 8.** The Alpha 7
> idea that manual AWAY must not count toward the aggregate was explicitly
> replaced. See [Alpha 8 aggregate](alpha8-aggregate.md): manual AWAY is
> authoritative and the home-empty binary result is ON iff everyone is AWAY.
> No production alarm automations were changed.

# Alpha 7 — household confidence safety gates (0.1.0a7)

**Shadow diagnostic build; not a production home-empty detector.**

## Why
Before exposing any all-away logic as a production automation source, the
internal model must distinguish a person's simulated AWAY state from reliable
evidence that the house is empty. In Alpha 6, manually forcing every member
AWAY could make the internal all-away method return True. This alpha
eliminates that unsafe inference without modifying any person's FSM
transition rules.

## New diagnostic sensor
`Family Presence Shadow - Diagnostica casa` is a regular **diagnostic** sensor,
NOT a binary sensor for alarm automation. Its states are:

- `presence_indicated`: one or more people have HOME/NEAR_HOME indicated;
  this does not claim verified occupancy if the state was manually forced.
- `candidate_empty`: all configured people have observed (not manually
  forced, not restored-only) AWAY states and there is no obvious contradictory
  available source evidence. This is a *hypothesis only*, not authority to arm.
- `indeterminate`: missing, restored, manual AWAY, contradictory or
  unavailable evidence prevents a candidate-empty report.

Attributes include `member_diagnostics` (member state + short reason),
`presence_indicated_members`, `unresolved_members`, `divergent_members`,
`all_away_internal`, `mode: shadow_only` and
`candidate_empty_is_not_alarm_permission: true`.

The shadow candidate-empty test refuses to rely on:
- Uninitialized states or snapshots not validated by a real new event
- `Forza fuori casa` button alone
- An iPhone still reporting `home`
- A Watch still detected via BLE
- All configured relevant sources being unavailable
- A bag ON without independent iPhone-outside evidence

After a manual AWAY or an unverified restored AWAY, a *new, genuine* iPhone
exit event can confirm the already-equal AWAY state and update its provenance.
This is not a new state transition and cannot be done with an unavailable
phone. The source adapter still requires an actual valid state change.

A bag still ON **does not permanently veto** a genuine iPhone-away event;
the bag may have been left at home. An AWAY value from the old YAML helper
is never used to seed or validate the new FSM.

## Still forbidden
No changes to the legacy YAML input_select helpers, alarm, locks, HVAC,
notifications or active presence automations. This release does not expose
a production `casa_certamente_vuota` binary sensor.

## Tests and safe verification
1. Check individual shadow states and their reasons after update/restart.
2. Open `Family Presence Shadow - Diagnostica casa`; review each blocker.
3. Press `Forza fuori casa` for a member who was HOME: the report must NOT
   become `candidate_empty` merely because of the button.
4. Later, let a genuine Watch/iPhone/bag event occur and review the new state.
5. Confirm a currently ON Watch or `home` iPhone prevents a candidate-empty
   verdict even if that person's previously stored state is AWAY.
6. Restart with every member in AWAY: unverified restored states must produce
   `indeterminate`.
7. Confirm the old YAML still controls every alarm/heating/notification action.

This diagnostic logic is intentionally conservative and may show
`indeterminate` when a person really is away. This is preferable to
arming an alarm on unverified data. More field evidence is necessary
before proposing any active integration.
