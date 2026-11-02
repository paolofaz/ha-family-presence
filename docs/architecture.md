# Runtime architecture — target design

This repository currently stores a config entry and pure rules only. There are **no active presence listeners, state entities, persistent runtime state or alarm side effects** in the scaffold. Do not remove the original working YAML yet.

## Layers

```text
Shared inputs: gate / door / lock / alarm
Person inputs: phone / Watch BLE / optional bag
                |
            sources.py                (planned)
      normalize events and quality
                |
       correlator / coordinator.py     (planned)
     timestamp windows + 2s Watch delay
     current evidence snapshot per person
                |
              fsm.py                  (pure, implemented)
        bag guard -> state transition
                |
           storage.py                 (planned)
    single writer + restart restoration
                |
      sensor.py / binary_sensor.py     (planned)
 raw FSM state, reason, timestamps,
         household all-away
                |
        downstream YAML automations
      alarm / heating / notifications
```

## Transition contract

Each member has a separate FSM (`home`, `near_home`, `away`). Phone exits/arrivals, Watch OFF/ON, gate/door/lock corroboration and bag changes match [baseline.md](baseline.md), except selected strict bag precedence in [bag-policy.md](bag-policy.md).

Watch OFF exit evidence is correlated with `last_seen_before_off` (gate <=120 seconds; door/lock <=90 seconds). Watch ON uses a 2-second delay and gate, opening and unlock evidence from <=120 seconds before evaluation. The engine must evaluate evidence at commit time, not cache it before sleeping.

Shared gate events alone never identify a specific household member. Physical gate/door/lock evidence can only corroborate a person-specific source. When a bag is confirmed absent under `always`, that constraint beats *all* entry hypotheses.

## Configuration

One household config entry. People are not hard-coded; each member has a stable internal identifier, display name, optional phone tracker, optional BLE watch, optional bag sensor and bag priority `always` or `legacy`. Shared sensors and timing windows are household-level. The initial UI currently stores people, sources, policy and correlation windows; mapping edits and runtime consumers remain to be implemented.

Future scheduled bag policy may expose days, school time ranges and holidays. It is deliberately not active until specified and tested.

## State and diagnostics

Suggested stable entities: one `sensor` per person with raw state and attributes for last reason, state-change timestamp, last evidence and conflict status; one all-away `binary_sensor` reporting true only when every tracked member is confidently AWAY. Surface user-facing text in translations; never overload raw state with zone descriptions.

Support manual override separately from sensor facts, with clear expiry and provenance. Persist the minimum required state and metadata across restarts; never replay an old gate event as new evidence. If source state is unknown, do not equate it to an absent person or bag. Event order is serialized per member to prevent a late BLE event overwriting a newer bag veto.

## Migration plan

1. Finish real-world bag sensor reliability and override behavior, then commit precise tests.
2. Implement coordinator and event adapter in shadow mode; do not write replacement presence entities or trigger the alarm until parity is demonstrated.
3. Add persistence and stable sensors, including conservative all-away and reasons.
4. Compare all four original people and a user-configured extra person; simulate HA restart, delayed Watch ON, source unavailable, shared gate and bag conflict.
5. Migrate downstream YAML to the new entities only after end-to-end verification.
6. Complete config edits, docs, HACS validation, Home Assistant Brands and releases before considering publication.

Alarm arming/disarming, heating reminder, unlocked-door warning and unrelated work-zone notifications remain in YAML. Family Presence must not call alarm, lock or heating services itself.
