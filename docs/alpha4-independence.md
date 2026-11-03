# Family Presence — Alpha 4: independent shadow FSM + Italian diagnostics

## Behavior and architecture

**The Family Presence FSM is fully independent of the legacy YAML presence helpers.** The previous versions initialized shadow presence from the old `input_select` and Alpha 3 consulted its state during snapshot restoration. That was useful during scaffolding but conceptually wrong for an independent replacement and could silently hide differences.

- The new coordinator **does not seed or restore presence from YAML**. Each person starts `unknown` on a fresh installation without a valid Family Presence snapshot, until the configured sensors provide a decisive event. A confirmed OFF bag in priority mode can establish AWAY during startup reconciliation.
- The FSM records and persists **its own** computed state, diagnostic reason and transition time in Home Assistant `.storage`.
- On restart, a compatible **shadow-owned** snapshot restores state/reason/time regardless of what the old YAML currently says. It is flagged `restored_from_storage: true` and is **not sufficiently fresh to establish `all_away=True`**; physical entry events and pending `near_home` age never carry over.
- The YAML `input_select` is now used **only for diagnostic comparison** (`legacy_state`, `matches_legacy`), and its value cannot affect transitions or stored explanations.
- Snapshot format **2** excludes the YAML comparison helper from the per-person source mapping fingerprint. Changing only the baseline does not clear the independent FSM. Format-1 snapshots from Alpha 1–3 are migrated where the original source mapping still matches.

## Italian-facing UI

The internal `always`/`legacy` policy values are preserved to keep existing configuration entries compatible. Their **visible labels** are:

- **Priorità assoluta** — a confirmed absent bag always forces away.
- **Fascia scolastica (lun–ven 07:00–09:10)** — the earlier weekday-morning bag exit behavior.

Both the initial config form and the per-person options form display these names. The diagnostic sensor's `bag_policy` attribute shows the Italian label; `bag_policy_code` retains the stable value for any technical debugging.

The sensor's `reason` attribute and the shadow transition logs now show **Italian** messages (e.g., `iPhone uscito dalla zona casa`, `Zaino rientrato`, `Zaino assente: priorità assoluta`). The FSM stores a stable machine-generated reason string and translates it only for presentation, so previously saved Alpha reasons remain readable without re-evaluating events.

## Migration / installation

1. Do not move the prior `v0.1.0a3` tag or delete the existing Home Assistant config entry.
2. Create a **new prerelease** tag `v0.1.0a4` from branch `chore/hacs-ready-foundation`.
3. In HACS, choose Family Presence → Download / Redownload → select `v0.1.0a4`, enable prereleases if necessary, and restart Home Assistant.
4. Existing mappings and person identities remain unchanged; confirm that shadow entities have Italian `reason`/`bag_policy` labels and, if a saved state was recovered, `state_origin=saved_shadow_unverified` and `reason_origin=saved_snapshot_unverified`.
5. Compare `legacy_state` / `matches_legacy` in Lovelace, **without interpreting a mismatch as a write or automatic correction**.
6. Reboot once later after a genuine new phone/Watch/bag decision: the shadow state and its reason should survive. If Alpha 2/3 already overwrote the old reason with null, Alpha 4 cannot reconstruct that past cause.

**Safety:** this alpha remains read-only. No production presence or all-away entities; YAML alarm/heating automations remain unchanged. A valid snapshot and all CI tests are **not** substitutes for checking behavior with actual Home Assistant sensors.
