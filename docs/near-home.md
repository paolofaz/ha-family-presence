# Decision record: should near_home remain?

Status: **keep current 3-state behavior during shadow validation**. No timeout or changed alarm behavior is enabled.

## What near_home actually represents

The original YAML's `near_home` is *not* an independent proof of a person being near the house. It is a **provisional, unconfirmed arrival**:

1. A Watch turns ON while the person is `away`; wait 2 seconds.
2. If a door opening, unlocking or gate event occurred recently (within 120s), the YAML moves directly to `home`.
3. Otherwise the same Watch ON moves to `near_home`.
4. While `near_home`, a subsequent gate opening, door opening or unlocking **plus Watch still ON** confirms `home`.
5. Watch OFF before confirmation moves `near_home` back to `away`.
6. An iPhone home-zone arrival or bag OFF→ON arrival can move `near_home` directly to `home` under current rules.
7. A confirmed absent bag in strict priority mode overrules all of these possibilities and forces `away`.

That third state prevents the system having to guess whether a lone BLE detection is definitively `home` or `away`. Removing it now would throw away meaningful pending evidence or inadvertently confirm occupancy.

## Implications for Home Assistant and alarms

In the original package, `binary_sensor.casa_certamente_vuota` is ON **only when every person is `away`**. Therefore `near_home` prevents the all-away result from becoming true; it does **not** count as a confirmed `home` return. The separate `familyrientro` YAML automation disarms on a transition **to `home`**, not `near_home`.

This is a deliberate conservative distinction, but can also defer all-away/arming indefinitely if `near_home` gets stuck. A BLE Watch left detectable without a confirming physical or phone event is a case to observe.

## Options discussed (not enabled)

| Policy | Pros | Risks |
| --- | --- | --- |
| Preserve near_home indefinitely (legacy) | No unverified inference; matches original package | Can stay provisional forever; may block all-away |
| Preserve with *diagnostic age only* (**current proposed design**) | Collects how long it lasts without changing decisions | Does not fix indefinite cases yet |
| Configurable near_home expiry to away | Resolves some stale pending states | May mark a person away who actually entered; can result in alarm arming |
| Remove near_home entirely | Simpler external interface | Must silently collapse uncertain BLE evidence into home or away; changes semantics |

**Selected now:** keep the FSM's existing states, measure observed `near_home` durations in shadow mode and add tests for all exit paths. Do not add a timeout or use a provisional near-home result to disarm the alarm.

## Shadow implementation

The coordinator records `near_home_entered_at` only after a **real shadow transition** to `near_home`. When it later transitions out, it reports `near_home_duration_seconds`, and HA logs a separate `[shadow][near_home]` resolution record. Pure diagnostic `near_home_age_seconds(person)` and `pending_near_home(min_seconds=...)` allow investigating prolonged states without changing them.

If a near-home state was copied from a YAML helper on restart, its prior duration is **unknown**; it must not be fabricated using the new process start time. Measurements begin after a fresh observed transition to near_home.

A future periodic checker could report pending provisional states above a user-configured warning threshold. The current code does not yet schedule this check or persist durations.

## Before deciding on a timeout

- Capture several actual Watch arrivals, including the Watch left charging near the BLE receiver.
- Check how often `near_home` resolves through iPhone vs door/unlock vs shared gate, and how long it typically lasts.
- Revisit whether an opening of a **shared condominium gate** should alone confirm `home` while the Watch is still detected: this is a separate confidence problem, even with near_home.
- Keep the all-away/alarm logic conservative until the risk of false absence has been tested.
- Reassess this decision after sufficient shadow logs, not by arbitrarily imposing a duration.
