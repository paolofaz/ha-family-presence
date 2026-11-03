# Safe shadow-mode field validation

Family Presence is experimental. **Do not remove the existing YAML package, rewire its state helpers, disable alarm automations or use experimental shadow sensors as alarm/heating triggers.** The integration in this PR publishes diagnostic-only simulated states and never sends services to alarms, locks or HVAC.

## Preparation

1. Back up your Home Assistant configuration, including `.storage` and the legacy YAML.
2. Install only the current draft `custom_components/family_presence/` as an experimental custom integration; do not treat the branch as a HACS release. Restart HA.
3. Add **Family Presence** from Devices & Services. Map common gate switch(es), door opening contact, door lock and optional armed-away alarm entity; set one member at a time.
4. For each person map their phone `device_tracker`, Watch `binary_sensor`, optional bag `binary_sensor`, and optionally the previous YAML `input_select` for **comparison only**, never for seeding or driving the FSM. Use actual entities visible in your Home Assistant instance; no private IDs appear here.
5. For people with a backpack choose **Priorità assoluta** (bag OFF veto at all hours) or **Fascia scolastica** (bag departure during weekdays 07:00–09:10). Underlying stored values remain `always`/`legacy`. BLE absence timeouts belong in the separate providers.
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
| Saved shadow `away` after restart, with or without valid YAML | State and previous explanation restored from shadow; internal all-away remains **unknown**, not certainly true |
| Restart when YAML and saved shadow disagree | Keep the **shadow-owned state and reason**; expose disagreement through `matches_legacy=false` only |
| Fresh install without a compatible shadow snapshot | Shadow state starts `unknown` until a source event or strict bag absence establishes an independent state |
| Restart when no saved reason exists | Keep the independent saved state, but `reason` stays empty rather than being invented |
| Change only the mapped old YAML comparison helper | Independent shadow snapshot remains compatible (format 3 in Alpha 5) |
| Premere Conferma in casa senza zaino, con zaino OFF | Lo shadow diventa HOME, deroga attiva, nessuna azione sull'allarme |
| Dopo 8 ore con deroga | Solo richiesta di revisione: mai passaggio automatico a AWAY |
| Revocare la conferma con zaino ancora OFF | Shadow unknown; vecchi eventi di cancello/Watch/zaino OFF non autorizzano AWAY |
| Riavviare con deroga attiva o dopo revoca | La conferma e il blocco di prudenza sono persistenti |
| Ritorno zaino a ON, anche da unavailable | La deroga termina; i normali eventi tornano a governare la FSM |

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
- Field-validate the experimental manual confirmed-HOME controls, conservative revocation and persistence after restart; do not use their states for production actions yet.
- Brand assets, release packaging, HACS validation.
