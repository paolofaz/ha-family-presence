# Family Presence for Home Assistant

A configurable, multi-person Home Assistant presence FSM using phone zone tracking, BLE wearables, physical gate/door/lock events, and optional bag sensors.

> **Experimental shadow build (0.1.0a5): DO NOT REPLACE YOUR EXISTING YAML.** The integration subscribes to HA inputs, records *shadow-only* state snapshots and exposes **diagnostic shadow sensors**, never production presence entities. It does **not** modify existing `input_select` values, or control alarm/locks/heating. It has not yet been end-to-end tested inside a running Home Assistant instance.

## Core behavior

- Per-person state `home` / `near_home` / `away`, with no fixed family size. New people receive immutable internal IDs independent of display names (old name-based entries remain compatible).
- Each person can map a phone tracker, Watch BLE sensor, optional bag sensor, a **legacy `input_select` reference** (for shadow comparison), and a bag priority policy.
- Shared gate switches/sensors, door contact, door lock and alarm are selectable.
- Event windows default to legacy values: Watch OFF: gate 120s, door/lock 90s relative to Watch `last_seen_before_off`; Watch ON: gate/door/unlock 120s, evaluated **after two seconds**.
- Bag policy `always` (the recommended default for a configured bag): a **currently OFF** bag forces `away` regardless of iPhone/Watch/door/gate. **OFF → ON** is a `home` event. With bag already ON, other sensors govern the FSM normally: bag presence does **not** permanently lock `home`.
- Bag policy `legacy`: the earlier behavior, with bag OFF causing departure only during the weekday 07:00–09:10 window; no precedence veto.
- `unknown` / `unavailable` is not OFF. Startup recovery does not invent arrival/departure transitions.
- `all_away()` is calculated internally, returning unknown if any person's state is unknown; **no all-away entity** is exposed and no shadow sensor should be used to arm/disarm alarms.

## Shadow setup (for safe testing)

1. Leave the original YAML package and all alarm/heating automations enabled.
2. Install the contents of `custom_components/family_presence/` under your HA `config/custom_components/family_presence/`. **This branch is experimental, not a release.**
3. Restart Home Assistant and add **Family Presence** under Settings → Devices & Services. Map the physical inputs and people.
4. Optionally select each person's old YAML `input_select` as **Legacy YAML presence helper**, strictly for diagnostic comparison. It **never seeds, modifies or controls** the independent shadow FSM.
5. The experimental `sensor.family_presence_shadow_...` entities can display the simulated state, last transition/reason, bag-policy conflict and comparison with the corresponding YAML helper. They are marked as **diagnostic**, have `mode: shadow_only`, and **must never be used as automation triggers**.
6. To see decisions and blocked false arrivals, enable info logs:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.family_presence: info
   ```

7. Review log entries `[shadow]` and `[shadow][blocked]`. They are **observations**, not state changes. No alarm automations should be switched over to this integration.

**Independent FSM and restart semantics:** the old YAML reference is display-only (`legacy_state`/`matches_legacy`) and never initializes the FSM, changes its state or authorizes a transition. The FSM decides from its configured phone/Watch/bag/physical sources and stores **its own state, reason and last-change time**. After a restart, a compatible saved shadow snapshot restores those fields regardless of whether the old YAML agrees. Restored occupancy remains marked `restored_from_storage` and is not proof for the internal `all_away=True` verdict. Without a valid saved snapshot the person starts `unknown` until a decisive observed event (or confirmed absent bag at startup). The source mapping and bag policy must match; changing only the legacy comparator no longer invalidates snapshots. Old format-1 snapshots are migrated. BLE/gate/door event history is intentionally **not restored**.

## Configuration policy: limited flexibility

Under **Settings → Devices & Services → Family Presence → Configure**:
- **Event correlation windows:** adjust the six gate/door/lock evidence windows. Values remain seconds, with the original YAML defaults.
- **Backpack priority:** choose a member with a bag, then **Priorità assoluta** (bag OFF forces AWAY at any time) or **Fascia scolastica** (old weekday 07:00–09:10 bag exit rule). The internal `always`/`legacy` values remain for compatibility; the UI and diagnostic `bag_policy` attribute now show Italian labels, with `bag_policy_code` carrying the stable raw value. Changes automatically reload the shadow integration.

Core FSM states, decision/event types, precedence between phone/Watch/physical inputs, and the two-second Watch observation delay remain in code, not user-defined expressions. The upstream Beacon BLE and Watch BLE absence timeouts are adjusted **only** in their respective integrations. Use **Reconfigure** on the integration entry (separate from Configure) to change shared entrance sensors, edit a member's mapped phone/Watch/bag/reference, add a member or remove a member. Each member keeps a stable internal ID and duplicated personal sources are rejected.

**Limitations:** log lines and diagnostic sensor comparisons include instantaneous legacy-state snapshots, not a synchronized parity report. HA event-adapter and new diagnostic sensor platform need real-world integration testing. Member/source entity edits now use Reconfigure; timing windows and backpack policies use Configure. Neither operation touches the original YAML. Additional bag debounce, production-ready manual override, production presence entities and all-away output are **not implemented**. Alpha 5 has only read-only shadow confirmation controls. Persisted shadow states are diagnostic-only and can be stale; a stored `away` state by itself never makes the internal all-away result true.

## Alpha 5 — Conferma manuale senza zaino (solo shadow)

Due pulsanti diagnostici per persona con zaino in **Priorità assoluta**:

- **Conferma in casa senza zaino:** disponibile se lo zaino è OFF. Convalida manualmente HOME nonostante lo zaino assente e salva la conferma immediatamente.
- **Revoca conferma senza zaino:** porta lo stato a non determinato, non ad AWAY. Il blocco di sicurezza sopravvive al riavvio finché non arriva una nuova prova di uscita (ad esempio un vero evento iPhone che lascia casa) o ritorna lo zaino.

L'eccezione non scade mai trasformando automaticamente HOME in AWAY. Dopo otto ore è prevista soltanto una **richiesta di verifica** tramite `manual_review_required`. Quando lo zaino torna ON, la conferma termina automaticamente. Le entità sono sperimentali e non comandano mai allarme, riscaldamento, serratura o stati YAML.

**Decisione rinviata al rilascio:** mantenere entrambe le modalità dello zaino o semplificare a una sola (issue #3).

## Files

- `custom_components/family_presence/fsm.py`: pure transition rules.
- `custom_components/family_presence/coordinator.py`: per-person serialized decisions, timestamp evidence, revisions, source fingerprinting and state snapshot export/restore.
- `custom_components/family_presence/labels.py`: Italian human-readable decision reasons and backpack policies (without changing stored backend values).
- `custom_components/family_presence/sensor.py`: read-only simulated presence state and diagnostic attributes (not for automations).
- `custom_components/family_presence/button.py`: pulsanti diagnostici per la conferma manuale senza zaino.
- `custom_components/family_presence/sources.py`: HA source subscriptions and normalization.
- `custom_components/family_presence/config_flow.py`: household/person mapping and options.
- `docs/baseline.md`: original YAML behavior.
- `docs/bag-policy.md`: bag precedence design and safety risks.
- `docs/near-home.md`: rationale for preserving provisional near_home, alarm implications, and shadow diagnostics.
- `docs/ble-sources.md`: reviewed beacon/Watch providers, 180s timing contracts and why not to merge all three integrations.
- `docs/architecture.md`: architecture, transition semantics and migration roadmap.
- `docs/shadow-test-plan.md`: safe real-world installation and validation checklist.
- `docs/alpha2-install.md`: Home Assistant helper-category fix and instructions for testing alpha 2.
- `docs/alpha3-restart.md`: historical Alpha 3 restart diagnosis.
- `docs/alpha4-independence.md`: independent FSM persistence, Italian diagnostics and Alpha 4 upgrade.
- `docs/alpha5-manual-bag.md`: eccezione manuale shadow e casi di sicurezza.
- `tests/`: pure unit tests; run `python -m unittest discover -s tests -v`.
- `.github/workflows/validate.yml`: unit tests, hassfest and HACS validation.

The private household-specific YAML is intentionally **not included** in this public repository. License: MIT.

HACS packaging layout is prepared, but a passing HACS validation, approved branding, and an actual release are still future work.
