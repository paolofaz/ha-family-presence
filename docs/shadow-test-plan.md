# Alpha 5 — field test: scheduled bag transitions and manual events

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
11. Observe `near_home` and shared condominium gate interactions. These
    require careful review before activating all-away in production.

A manual force-away will matter for a future live all-away sensor, so perform
these tests without wiring shadow outputs to any alarm or door automation.

If a problem occurs, disable Family Presence only; leave the separate BLE
providers and the original YAML intact. Record anonymized source timestamps,
states and reasons for any disagreement.
