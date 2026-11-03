# Alpha 9 — field test: persistence, bag schedule and event diagnostics

**Leave the old family YAML package and all alarm/lock/heating automations
enabled.** Only use diagnostic shadow entities and buttons. Do not use these
for production automation triggers.

1. Verify all four shadow sensors are present and compare `legacy_state`
   with the independent FSM state and `reason`.
2. Under **Configure → Backpack schedule**, review each bag's schedule.
   Old `always` preferences migrate to full-day; old `legacy` preferences
   migrate to 07:00–09:10 weekdays.
3. Observe a real bag ON→OFF *inside* the scheduled hours: shadow becomes
   AWAY. Outside the configured hours it should not change.
4. Observe a real bag OFF→ON at any hour: shadow becomes HOME.
5. While a bag is already OFF, observe a new valid iPhone/Watch event: a new
   event may change the FSM normally; there is **no permanent bag veto**.
6. Disable one bag schedule in Configure (if desired for testing): no bag
   transition should change state, while phone/Watch continue normally.
7. Confirm that OFF due to `unknown/unavailable→off` or at boot does not
   synthesize an exit; `unknown→on` does not synthesize an arrival.
8. Press **Forza a casa** for one person, then wait for a naturally occurring
   new source event; the later event may change the state.
9. Press **Forza fuori casa** during a safe test, verify only the shadow state
   changes. Check that no YAML or alarm state changes because of the button.
10. Reboot after a manual action: shadow state and reason should return from
    Family Presence's own snapshot, marked `restored_from_storage`.
11. In the new sensor attributes verify `comparison_status`, `divergence_since`,
    `last_ignored_event`, `last_ignored_reason` and `recent_events`. An outside-window bag OFF
    should be logged as ignored, without changing presence.
12. After upgrading from Alpha 5, verify state restore, change only a bag's
    configured schedule, then reload: HOME/AWAY should survive both operations.
    A deliberate source-entity remap may require re-establishing shadow state.
13. Observe `near_home` and shared condominium gate interactions. These
    require careful review before activating all-away in production.

A manual force-away will matter for a future live all-away sensor, so perform
these tests without wiring shadow outputs to any alarm or door automation.

If a problem occurs, disable Family Presence only; leave the separate BLE
providers and the original YAML intact. Record anonymized source timestamps,
states and reasons for any disagreement.

14. Inspect **Family Presence Shadow - Casa certamente vuota**, which must
    be ON iff all configured people are AWAY. Do not wire it to the alarm.
15. Force the last HOME person AWAY: shadow binary sensor must immediately
    turn ON. Force that person HOME: it must immediately turn OFF.
16. Make the last person's state NEAR_HOME or unknown: aggregate stays OFF.
17. Restart with all people AWAY: restored AWAY states still yield ON.
18. Contradictory iPhone/Watch sources may appear under `source_warnings`
    but must not override manual force in the aggregate.
19. Compare the new shadow binary sensor with the production YAML
    `binary_sensor.casa_certamente_vuota`, keeping YAML the sole writer.

20. In the new shadow binary sensor, verify `legacy_comparison_status`,
    `legacy_expected_all_away`, `aggregate_matches_legacy` and
    `legacy_differing_members`. These use the mapped old
    `input_select.presenza_*` references, not the live binary sensor.
21. When all four shadow and legacy members are AWAY, comparison must be
    `aligned`. Force one shadow member HOME: comparison should show
    `aggregate_divergence`; force them AWAY again to clear it.
22. If the aggregate is OFF in both engines but different people are
    HOME/AWAY, `member_divergence` must identify the names.
23. If one old reference helper is missing or unavailable, parity must
    report `not_configured` or `reference_unavailable` instead of matching.
24. Confirm `legacy_divergence_since` starts on mismatch and clears on
    alignment. Never use any shadow entity to trigger the alarm.
