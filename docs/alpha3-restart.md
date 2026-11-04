# Family Presence v0.1.0a3 — Alpha 3 / shadow restart diagnostics

## What happened in Alpha 2

A real Home Assistant restart revealed that the shadow state could correctly return to `away` while its previous explanation (e.g. `iPhone left home zone`) disappeared.

**Root cause:** the shadow coordinator started from the currently valid legacy YAML `input_select` and deliberately skipped *all* saved shadow data for that person. This correctly preserved occupancy priority but unintentionally dropped the already-saved historical `reason` and `last_changed` fields. On next state/source updates, an empty reason could overwrite those fields in `.storage`, so the original explanation might then be unrecoverable.

## Fix

1. The currently valid legacy helper still has priority for **state**.
2. A saved snapshot is accepted only if its person/source/bag-policy fingerprint matches. If the saved state also equals the current YAML state, restore **only historical diagnostic reason and original last-transition timestamp**, not the state itself.
3. If the saved state conflicts with YAML, discard the saved cause; never attach an old iPhone/bag event to an unrelated live state.
4. If YAML is missing/unavailable, the matching snapshot can restore state, but stays flagged as **unverified** and cannot establish a certain all-away verdict.
5. Add `state_origin` and `reason_origin` diagnostic attributes. Key values: `legacy_reference`, `saved_shadow_unverified`, `observed_transition`; and `observed_event`, `saved_snapshot_matched_legacy`, `saved_snapshot_unverified`, `not_recorded`.
6. Reconciliation still does not create fake iPhone, bag or gate events.

**Limits:** Alpha 3 cannot resurrect a reason already erased by Alpha 2, and even a correctly saved reason may be out of date when the legacy helper changed before shadow processed the event. A reason is a diagnostic provenance record, not an alarm authorization.

## Upgrade

Create a **new prerelease tag** `v0.1.0a3` targeted at `chore/hacs-ready-foundation`. Do not repoint or delete the older `v0.1.0a2` tag.

In HACS open Family Presence → Download / Redownload → select `v0.1.0a3` (enable beta versions if needed), then restart Home Assistant. Existing Family Presence config entries and four person/sensor mappings should be retained. Verify the shadow entities' `reason_origin` on restart: a matching previously saved reason should say `saved_snapshot_matched_legacy`; an unknown cause says `not_recorded` until an actual new decision.

No production alarm, heating, lock or presence helper is modified. Leave the YAML package active.
