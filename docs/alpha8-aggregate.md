# Alpha 8 — authoritative FSM aggregate (0.1.0a8)

## Product decision

**Casa certamente vuota = ON if, and only if, every configured member's
FSM state is `away`. Otherwise it is OFF.** This reproduces the existing
family YAML template exactly, with one important rule clarified explicitly:
a manual force is an **authoritative state transition**, not a tentative
observation. It counts exactly like any other HOME/AWAY state and remains
in effect until a *later valid* FSM event changes that person.

Truth table:

| FSM state set | Aggregate |
| --- | --- |
| All members `away`, however assigned | `on` |
| One or more `home` | `off` |
| One or more `near_home` | `off` |
| One or more `unknown`/not yet initialized | `off` |
| Zero configured members (defensive) | `off` |

An AWAY restored from the integration's own snapshot also counts as AWAY;
a restart should not silently override a known persisted decision. If a
stored snapshot is rejected due to remapped sources, its member becomes
unknown and the aggregate is OFF until a new decision is made.

## What changed from Alpha 7

Alpha 7 attempted to use independent sensor confidence to veto the
all-away aggregate, including manual AWAY. That was intentionally
superseded after the desired behavior was clarified. **Sensor conflicts
do not change the aggregate.** They remain visible in a separate
diagnostic `source_warnings` structure.

The existing per-person FSM and two one-shot force buttons continue to
work unchanged. A later valid phone/Watch/bag event may supersede the
manual state, and the aggregate immediately follows the resulting state.

## Home Assistant entities

- **New** `binary_sensor` diagnostic: *Family Presence Shadow - Casa
  certamente vuota*. Its `on`/`off` value is exactly the above
  aggregation. Attributes include per-person state and reason.
- *Family Presence Shadow - Diagnostica casa* shows `all_away`,
  `presence_indicated` or `incomplete`, with `member_diagnostics`,
  `unresolved_members`, `divergent_members` and `source_warnings`.

**Neither is the legacy production entity** `binary_sensor.casa_certamente_vuota`.
All existing alarm, heating and notification automations continue to
reference the original YAML binary sensor. Pressing the new shadow force
button updates ONLY the new shadow aggregate; it does not currently
change the original YAML input_select or arm/disarm the alarm.

## Required field tests before a production cutover

1. Confirm all four members' shadow sensors reflect normal real events.
2. Force each remaining HOME member AWAY, one by one: the shadow
   all-away binary sensor turns ON exactly when the final member is AWAY.
3. Force any one member HOME: it immediately turns OFF. Force that
   member AWAY again: it turns ON.
4. Verify a member in NEAR_HOME, unknown or unavailable snapshot causes OFF.
5. Restart with all AWAY: all shadow states restore and aggregate stays ON.
6. Verify a later genuine phone/Watch/bag event can supersede a manual
   state, and the binary sensor follows it.
7. Compare shadow and YAML aggregate while the old YAML is still the
   sole controller of production `casa_certamente_vuota` and alarm.
8. Do not attach the shadow sensor to any alarm or lock automation until
   the explicit cutover plan is tested and approved.

The integration remains experimental shadow-only. The exact aggregate
semantics are now settled, but operational cutover is deliberately separate.
