# Family Presence architecture — independent shadow FSM

## Data flow

Phone tracker + Watch BLE Presence + Beacon BLE Presence + physical gate/door
events → `sources.py` (verified state changes/timestamps) →
`coordinator.py` (per-person locks, source revisions, schedule at event time) →
`fsm.py` (three-state deterministic transitions) →
diagnostic-only `sensor.py`, one-off `button.py`, private HA Store snapshot.

A fifth, diagnostic-only household sensor reports `presence_indicated`,
`candidate_empty` or `indeterminate` with a reason per person. Even
`candidate_empty` is a **shadow hypothesis**, not a production permission
to arm an alarm. A manual force-AWAY, a restored state, an iPhone still
`home`, a Watch still detected, or missing source availability prevents
`candidate_empty`. An active bag ON without independent iPhone-outside
evidence also prevents that claim. Manual HOME blocks an empty-house verdict.

The original YAML `input_select` is optional and read for
`legacy_state`/`matches_legacy` only. No old YAML helper seeds, overrides or
writes the independent FSM.

## State and precedence

Phone zone: HOME/AWAY. Watch ON from AWAY requires gate/door/lock evidence or
becomes provisional NEAR_HOME; Watch OFF uses prior evidence relative to
`last_seen_before_off` or the phone/alarm. Shared condominium gate events
cannot identify a person on their own.

A configured bag provides two **events**: OFF→ON HOME at any time; ON→OFF AWAY
only in its enabled and configured local time/day window. Bag OFF **is not
a permanent veto**. The next valid sensor event may update the state.

Two buttons per person, Forza a casa / Forza fuori casa, generate immediate
manual FSM events, stored and logged. Neither has continuing priority. An
automatic callback older than the last manual event cannot roll it back.

## Schedule and migration

The per-person `BagSchedule` object contains boolean enabled, start/end clock
times and weekday numbers 0–6. Equal start/end means full day; crossing
midnight checks the previous day's eligibility for the after-midnight portion.

New user-facing schedule replaces the old `always`/`legacy` policy choice.
Old options map to 24h/all-days or weekdays 07:00–09:10 respectively. The
old policy code is used **only** for migration of earlier Alpha snapshots,
not in the FSM decision logic.

Source mapping is configurable separately. Members get stable IDs and can be
renamed without changing entity identity. Bluetooth source timeout settings
remain owned by their dedicated HA BLE integrations.

## Restart and confidence

Snapshot **format 5** fingerprints source mappings (iPhone/Watch/bag) alone.
Departure schedule edits no longer erase the saved shadow state. It also stores
state, reason, transition time, last manual action and last ignored event.
Old formats 1–4 can be read when their original fingerprints still match.
Alpha 5 format-4 snapshots are converted immediately on successful first load;
an arbitrary schedule edit before that conversion cannot be validated safely. Old persistent manual bag holds are **not restored as holds**.
No previous physical gate/door events are restored.

Restored states are marked `restored_from_storage`. A per-person diagnostic
records ignored input events and tracks YAML/shadow mismatches without
changing FSM decisions. The conservative internal
`all_away()` does not return true based solely on saved away states, and
near-home blocks certain emptiness. Alpha 7 also excludes manually forced
AWAY and contradictory/unavailable sources from the internal verdict.
Only a diagnostic household sensor is exposed; **no production all-away binary
sensor or production presence output** exists.

## Safety boundary

This alpha has no service calls to alarm, lock, HVAC or YAML helpers. Continue
field validation with real devices, including delayed/offline BLE, false
departures, event order, schedule boundaries and button press followed by a
later sensor event. The existing YAML actions remain the only production
alarm/heating controls.
