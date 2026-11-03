# Alpha 9 — automatic YAML/shadow parity report (`0.1.0a9`)

## Goal

Make the side-by-side test of the two independent machines measurable.
The original YAML remains authoritative for all production actions. The
new Python FSM stays in **shadow-only** mode, with the user-defined rule:

**Casa certamente vuota = ON exactly when every person's FSM is AWAY,
including manual overrides and restored AWAY.** Otherwise OFF.

## What is compared

The old family YAML computes `binary_sensor.casa_certamente_vuota` as
the logical AND of the four `input_select.presenza_*` values equal to
`away`. Alpha 9 reconstructs that **expected** result from the optional
old `input_select` reference already mapped for each member.

This does **not** read the live `binary_sensor.casa_certamente_vuota`
and does **not** change any legacy input_select. If the helper
configuration is incomplete or currently unavailable, the comparison
status says so.

The preview binary sensor
*Family Presence Shadow - Casa certamente vuota* exposes:

| Attribute | Meaning |
| --- | --- |
| `legacy_comparison_status` | Whether the two FSMs agree |
| `legacy_expected_all_away` | Predicted ON/OFF of the old template from mapped helpers |
| `aggregate_matches_legacy` | True/False when every reference is readable |
| `legacy_differing_members` | Names whose individual states disagree |
| `legacy_member_states` | Each configured old helper's present state |
| `legacy_divergence_since` | Beginning of the current mismatch, or null |
| `legacy_missing_reference_members` | Members without a configured old helper |
| `legacy_unavailable_reference_members` | Members with an unreadable old helper |

Comparison results:

- **aligned:** all individual states and both aggregate results agree.
- **member_divergence:** person states differ but both aggregate results
  are the same (useful for cross-swapped HOME/AWAY states).
- **aggregate_divergence:** the two results for Casa certamente vuota differ.
- **not_configured:** at least one legacy comparison mapping is missing.
- **reference_unavailable:** a configured legacy helper has no valid
  `home`, `away` or `near_home` reading.

`legacy_divergence_since` is tracked only while comparison data is valid,
in the **current integration runtime**. Restarting the integration resets
the comparison clock: it does not invent elapsed time it never observed.
Changing the old YAML helper refreshes this report immediately through
the existing read-only source listener.

## Safety and scope

There are no new actuator calls, writable presence entities, lock/alarm
actions, new Bluetooth timeouts or changes to the individual FSM's source
event priorities. Shadow diagnostic sensors remain distinct from the
production YAML entities.

## Field tests

1. Verify all four people have the correct old `input_select` reference
   mapped in Family Presence.
2. Observe the new shadow binary sensor's parity attributes.
3. With two different but equally nonempty people states, verify
   `member_divergence` rather than false alignment.
4. Force the last shadow member HOME/AWAY and confirm aggregate parity
   reacts without changing the old YAML.
5. During natural Giulia/Arianna bag transitions, inspect differing
   members and divergence start timestamps.
6. Restart Home Assistant and verify shadow state persistence, aggregate
   ON/OFF rule, and parity refresh after startup.

**Do not connect any shadow binary/sensor to alarm automations.**
