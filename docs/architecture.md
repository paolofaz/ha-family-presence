# Family Presence architecture — independent shadow FSM

## Data flow

Phone tracker + Watch BLE Presence + Beacon BLE Presence + physical gate/door
events → `sources.py` (verified state changes/timestamps) →
`coordinator.py` (per-person locks, source revisions, schedule at event time) →
`fsm.py` (three-state deterministic transitions) →
diagnostic-only `sensor.py`, one-off `button.py`, private HA Store snapshot.

The diagnostic-only aggregate binary sensor replicates the legacy YAML
truth table: `on` iff every configured person's state is `away`. Manual
force AWAY and restored AWAY count as authoritative states. HOME, NEAR_HOME
and unknown always make the aggregate `off`. Live source contradictions
and YAML differences are tracked as diagnostic warnings only, not vetoes.
The independent diagnostic household sensor explains current state inputs.

Both sensors are shadow-only. No production all-away entity exists in this
integration, and the original YAML still owns the real `casa_certamente_vuota`.

The original YAML `input_select` is optional and read for
`legacy_state`/`matches_legacy` only. No old YAML helper seeds, overrides or
writes the independent FSM.

## State and precedence

Phone zone: HOME/AWAY. Watch ON from AWAY requires gate/door/lock evidence or
becomes provisional NEAR_HOME; Watch OFF uses prior evidence relative to
`last_seen_before_off` or the phone/alarm. Shared condominium gate events
cannot identify a person on their own.

A configured bag provides two **events**: ON→OFF may establish AWAY only
inside its configured local time/day window; OFF→ON may establish HOME at any
time only when an earlier accepted BAG_LEFT caused AWAY. The coordinator stores
a per-person `bag_return_eligible` provenance flag (not a reason string).
It remains valid through Watch-caused NEAR_HOME, but clears when a new iPhone,
Watch or manual event supersedes the bag departure. Bag OFF **is not
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

## Aggregate and individual YAML parity

`comparison.py` rebuilds the old YAML's logical all-away result from the
**configured per-member comparison helpers**. It never seeds or alters the
new FSM. A missing/unavailable helper results in an explicit unverified
comparison, not a guessed match. It separates aggregate disagreement from
per-person disagreement while both aggregates remain equal.

The per-runtime `parity_diverged_since` records the start of a continuous
verifiable mismatch and resets on alignment or unavailable references.
The diagnostic shadow binary sensor exposes the result alongside individual
state reasons. The live legacy production binary sensor may be optionally mapped for
read-only parity checking in Beta 1; it is never used for FSM decisions.

## Restart and confidence

Snapshot **format 5** fingerprints source mappings (iPhone/Watch/bag) alone.
RC6 adds an optional boolean `bag_return_eligible` to that same format, which
new snapshots persist. Earlier snapshots without it fail closed, leaving the
previous presence state intact until an independent event or a new bag trip.
Departure schedule edits no longer erase the saved shadow state. It also stores
state, reason, transition time, last manual action and last ignored event.
Old formats 1–4 can be read when their original fingerprints still match.
Alpha 5 format-4 snapshots are converted immediately on successful first load;
an arbitrary schedule edit before that conversion cannot be validated safely. Old persistent manual bag holds are **not restored as holds**.
No previous physical gate/door events are restored.

Restored states are marked `restored_from_storage`. A per-person diagnostic
records ignored input events and tracks YAML/shadow mismatches without
changing FSM decisions. The internal `all_away()` returns a strict boolean:
TRUE iff all member states are AWAY, regardless of manual/restored origin.
A diagnostic shadow binary sensor exposes that result, but **no production
all-away binary sensor or production presence output** exists.

## Safety boundary

This alpha has no service calls to alarm, lock, HVAC or YAML helpers. Continue
field validation with real devices, including delayed/offline BLE, false
departures, event order, schedule boundaries and button press followed by a
later sensor event. The existing YAML actions remain the only production
alarm/heating controls.

## RC7: public entity payload and Recorder noise

Production member sensors expose only state, translated reason, last actual
state transition, and optional backpack return eligibility. The all-away
binary sensor has no extra state attributes. Household diagnostics only
publish source warnings when present. Detailed ignored-event counters,
source values and debug trails remain internal and are never exposed on
production person sensors.

The public sensor and aggregate entity callbacks cache their last visible
(state, attributes) pair. Even if the coordinator notifies a listener about an
ignored event or a BLE source change, the entity avoids a redundant
`async_write_ha_state` unless its visible output changed. No clock-driven
or per-second public attributes exist. History already stored in Home
Assistant Recorder is not deleted by this change.
