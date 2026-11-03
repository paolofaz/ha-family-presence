# Backpack schedule — event-based behavior (Alpha 5)

This replaces the earlier two backpack priority modes. No permanent bag-off
guard, no school-only policy switch, no eight-hour manual hold.

## Single rule

- **ON→OFF**: if enabled and this event timestamp falls inside the configured
  local time window *and* selected weekday, set **away**, even if phone/Watch
  evidence disagreed immediately before this event.
- **OFF→ON**: if enabled, set **home** at any time, independent of the configured
  departure schedule.
- **OFF steady**: does **not** veto later phone/Watch/door events. A later
  valid event can set home or away using the normal FSM.
- **Disabled**: both bag transitions are ignored by Family Presence.
- **unknown/unavailable→on/off**: not a real bag transition, so no automatic
  home/away. A reboot finding the bag already OFF does not synthesize departure.

## Options

Per-person schedule has `enabled`, `start`, `end`, `days`.
Dates are evaluated in the Home Assistant timezone at the **HA event time**,
not when the asynchronous queue happens to process the event.

- 07:00–09:10, Mon–Fri: school window.
- 00:00–00:00, all days: always enabled for departure.
- 22:00–02:00, Monday: Monday evening through Tuesday 01:59.
- Enabled = false: disable the bag entirely.

The independent BLE source applies its own 180s absence timeout; this FSM
responds when its binary sensor actually transitions to OFF. We must still
evaluate false OFFs and the blind period before the provider publishes OFF.

## Manual correction

Two buttons per person set a one-off `home` or `away` decision. They do not
lock the state or change the backpack's schedule. After an explicit button
press, the next **new** Watch, phone or bag event can change the state.

## Migration

Previously configured `always` maps to a 24h/all-days schedule,
`legacy` maps to weekday 07:00–09:10. These values remain internal solely
for reading existing Alpha snapshots/configuration; they are no longer
user-facing options or FSM precedence modes.

## Critical alarm safety note

This is shadow-only. A future production force-away button could contribute
to a claim that the house is empty. Until all-away confidence and automation
behavior are validated, do not use these buttons or diagnostic sensors to
arm or disarm any alarm.
