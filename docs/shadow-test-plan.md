# Safe shadow-mode field validation

Family Presence is experimental. **Do not remove the existing YAML package, rewire its state helpers, disable alarm automations or use experimental shadow sensors as alarm/heating triggers.** The integration in this PR publishes diagnostic-only simulated states and never sends services to alarms, locks or HVAC.

## Preparation

1. Back up your Home Assistant configuration, including `.storage` and the legacy YAML.
2. Install only the current draft `custom_components/family_presence/` as an experimental custom integration; do not treat the branch as a HACS release. Restart HA.
3. Add **Family Presence** from Devices & Services. Map common gate switch(es), door opening contact, door lock and optional armed-away alarm entity; set one member at a time.
4. For each existing family member, map their phone `device_tracker`, Watch `binary_sensor`, optional backpack `binary_sensor`, and the relevant legacy `input_select` reference. Use the actual entities visible in your HA installation; examples do not include private entity IDs.
5. For members with a backpack, choose `always` if you want confirmed bag absence to override Watch/phone and the shared gate; choose `legacy` to compare the original YAML behavior. Absence timeouts remain in Beacon BLE Presence / Watch BLE Presence.
6. In the integration's **Configure** menu, verify the default window values (exit gate=120s, door=90s, lock=90s; entry gate/door/unlock=120s). **Reconfigure** changes source entities and household members without recreating the entry.
7. To include simulated decisions in logbook diagnostics, enable an INFO logger for `custom_components.family_presence` via Home Assistant's logger configuration. **Never include raw IRKs, iBeacon identifiers, access tokens or your private URL in issue reports.**

## Observe; do not force security-sensitive actions

| Scenario | Expected experimental behavior |
| --- | --- |
| Bag `on→off` after the upstream 180s BLE absence timeout | The shadow person becomes `away` in strict mode |
| Watch `off→on` while bag confirmed `off` | Entry is rejected; shadow remains `away`, with a blocked event reason |
| Bag `off→on` | Shadow becomes `home` |
| Bag already `on`, phone leaves home zone | Normal FSM may become `away`; bag ON is not a HOME lock |
| Watch `off→on` from `away` without physical corroboration | Shadow enters `near_home`; leaving Watch range can return it to `away` |
| Watch `on→off`, phone inside | Exit needs suitable physical event within the existing window **before last_seen_before_off** or armed-away alarm evidence |
| Old gate/door evidence after HA restart | Cannot be replayed as an arrival |
| Bag starts up `unavailable→off` | Reconcile priority only, not a synthetic physical off-event |
| Rename member / swap selected Watch / remove member | Shadow configuration reloads; stable identity remains for a rename and stale evidence is not inherited across changed source mappings |
| Previously saved shadow `away` with no valid live legacy helper | Internal all-away is **unknown**, not confirmed true |

Caution: the strict bag veto takes effect only after the *upstream* bag sensor actually reports `off`. A physically absent bag may remain `on` for about three minutes. Watch BLE has its own configured 15s polling / 180s timeout. A shared condominium gate event is corroboration, not identity.

## What to collect

Capture a few anonymized sequences: member's reference YAML state, shadow state, event type, event/Watch-last-seen timestamps, elapsed Watch/Beacon timeout, and the reason or bag-conflict attribute. Track how often `near_home` lasts unusually long. Record any differences **after both automations have had time to process**. An immediate shadow-versus-YAML snapshot does not prove parity.

## Stop / rollback

- If the experimental integration fails setup, unload or produces unexpected diagnostics: disable or remove **only Family Presence**, then restart HA if needed. Leave BLE providers and original YAML intact.
- No other integration should require Family Presence at this stage. Keep existing all-away/alarm automations using the original YAML helpers.
- Do not transition to production presence entities or connect alarm automations until manual override, unavailable-source behavior, and end-to-end live integration tests have been signed off.

## Remaining engineering gates

- Real HA setup/teardown and repeated reload test on a supported version, not only mocked adapter tests.
- Stable persistence through HA restart and source provider delayed startup.
- Time-aligned parity report / diagnostic history for discrepancies.
- Manual confirmed-home exception design when a child enters without their backpack; avoid auto-returning to away upon unsafe expiry.
- Brand assets, release packaging, HACS validation.
