# Alpha 6 — persistence and diagnostic reliability (0.1.0a6)

## Scope
This is a shadow-only release. Original family YAML remains the sole writer of
presence helpers and the sole controller of alarm, locks, HVAC and notifications.
No migration of production automations or production all-away entities.

## Fix: backpack schedule edit no longer resets shadow presence
Snapshot format 5 validates stable person ID and configured **source entities**
(phone, Watch and bag) but does not use the bag departure schedule as a state
identity constraint. Changing bag-enabled/hours/days therefore retains a
previously saved HOME/AWAY/NEAR_HOME state. Source entity remapping still
invalidates the old stored state for safety. A restored AWAY remains unverified
and cannot alone establish certain emptiness.

Format 1–4 snapshots remain readable under their original fingerprint rules.
A valid Alpha 5 format-4 snapshot is converted to format 5 immediately at first
successful Alpha 6 load, *before* the next Configure reload. If an Alpha 5
snapshot is already incompatible with its source and schedule settings, this
release cannot infer the lost state. Perform the upgrade without simultaneously
changing the schedule; verify the successful restore before editing options.

## Explain ignored inputs
New shadow diagnostic attributes:
- `last_ignored_event`: last event intentionally discarded
- `last_ignored_reason`: short reason in Italian
- `last_ignored_at`: timestamp of input event
- `ignored_event_count`: total count (persisted with format 5)

Examples: bag OFF outside the departure window, disabled bag, stale source
callback, Watch transition without adequate evidence, unknown/unavailable bag
sensor recovery. Rejected input never updates the person's presence.

## Bounded decision log
The diagnostic attribute `recent_events` exposes the last 12 accepted or
ignored transitions with their event name, outcome, event time, state and
reason. The scrubbed list is stored with snapshot format 5. It is never
replayed to set presence on restart.

## Comparison diagnostics
New `comparison_status` attribute: `aligned`, `diverged`, `unknown`, or
`not_configured`. New `divergence_since` records the start of a continuous
difference between the independent shadow state and the optional YAML reference.
Comparison changes are read-only: no automatic corrections, notifications or
alarm actions. The existing `matches_legacy` attribute stays available.

## Smoke tests in Home Assistant
1. Upgrade while keeping the existing bag schedule unchanged; restart.
2. Verify the four shadow sensors restore their previous states and reasons.
3. Change only Giulia's bag schedule and reload; confirm she retains her state.
4. Repeat with Arianna. Test an actual bag OFF outside/inside its schedule.
5. Inspect the new ignored-event attributes and mismatch timestamp.
6. Press one manual HOME/AWAY button, restart, and verify persistence.
7. Confirm YAML and alarm continue to behave exactly as before.

Do not connect shadow sensors or manual force buttons to production alarm
automations. If a field test fails, disable only Family Presence; keep the
original YAML active.
