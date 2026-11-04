# Family Presence Alpha 5 — redesign of backpack and manual controls

This supersedes the unreleased prototype with a persistent manual-home hold.

## Replaced

- Removed both user-facing bag policy options (`always`/`legacy`).
- Removed the persistent bag OFF veto and startup absence reconciliation.
- Removed the old manual home-without-bag / revoke-into-unknown buttons and
  their eight-hour review/hold behavior.

## New semantics

An enabled bag's **ON→OFF** only sets AWAY inside its configured departure
time window and weekdays; **OFF→ON** always sets HOME. Neither has persistent
precedence, and later valid phone/Watch events may change the FSM. Turning a
bag off in options ignores both directions. An equal start/end time such as
00:00–00:00 means full day; overnight windows are supported.

Every person, with or without a bag, gets **Forza a casa** and
**Forza fuori casa** diagnostic buttons. Each creates a one-off change,
persisted immediately, without overriding later real source events. The
integration still never calls an alarm, lock or other device service.

Existing bag `always` preferences are migrated to 24h/all-days schedules,
and `legacy` to weekday 07:00–09:10. The old codes are used solely for
snapshot/config migration, not FSM decisions. Snapshot format is now 4.
After migration, verify the displayed schedule before field testing.

## Production gates

The new manual force-away could eventually contribute to an all-away verdict.
A production all-away sensor and alarm migration are **not** included in
this release. First check behavior under genuine BLE updates, source
unavailability, schedule boundaries, manual buttons and restart.
