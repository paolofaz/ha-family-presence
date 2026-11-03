# Family Presence architecture — independent shadow FSM

## Data flow

Phone tracker + Watch BLE Presence + Beacon BLE Presence + physical gate/door
events → `sources.py` (verified state changes/timestamps) →
`coordinator.py` (per-person locks, source revisions, schedule at event time) →
`fsm.py` (three-state deterministic transitions) →
diagnostic-only `sensor.py`, one-off `button.py`, private HA Store snapshot.

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

Snapshot **format 4** includes a fingerprint of source mappings and bag
schedule plus FSM-owned state, reason, transition time and last manual action.
Old snapshot formats 1–3 can be read using a legacy fingerprint, when mapping
still matches. Old persistent manual bag holds are **not restored as holds**.
No previous physical gate/door events are restored.

Restored states are marked `restored_from_storage`. The conservative internal
`all_away()` does not return true based solely on saved away states, and
near-home blocks certain emptiness. No actual all-away binary sensor or
production presence output has been exposed yet.

## Safety boundary

This alpha has no service calls to alarm, lock, HVAC or YAML helpers. Continue
field validation with real devices, including delayed/offline BLE, false
departures, event order, schedule boundaries and button press followed by a
later sensor event. The existing YAML actions remain the only production
alarm/heating controls.
