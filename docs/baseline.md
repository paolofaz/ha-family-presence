# Behavioral contract extracted from current YAML package

This baseline is descriptive; no rule is changed by this initial PR. The source YAML is not published, because it contains private person names and entity IDs.

## States

Every configured person has home, near_home and away, a reason, and change metadata. In the current four-person YAML, casa_certamente_vuota becomes true only when all four states are away.

## Transitions

| Input event | Required state / evidence | Result |
| --- | --- | --- |
| Phone leaves home zone | State not already away, destination valid | away |
| Phone enters home zone | State not already home, origin valid | home |
| Watch ON | From away, after 2-second delay | home if physical opening/unlock/gate recent; otherwise near_home |
| Watch OFF | From home, phone outside OR physical exit evidence OR alarm armed away | away |
| Watch OFF | From near_home | away |
| Gate / door open / unlock | near_home AND Watch ON | home |
| Bag ON | Any | home, even if previously home |
| Bag OFF | Weekdays 07:00 to 09:10 local | away |

Exit physical evidence must be <=120s (gate), <=90s (door closed) or <=90s (lock) **before Watch last_seen_before_off**, not simply before the OFF trigger. Reason priority: phone outside, gate, door close, lock, armed-away alarm.

Arrival evidence uses <=120s windows relative to Watch ON processing. Reason priority: door open, unlock, gate. Watch ON waits two seconds first.

Bag arrival changes to home unconditionally. Bag departure changes to away only within the school window. **These potentially surprising semantics must remain the baseline until the bag issue is reviewed.**

The last-change timestamp helper only updates on display-state transitions involving In casa, not every FSM change.

## Downstream automations to keep in YAML

- Warning after 2 minutes when everyone is away and door not locked.
- Heating reminder on all-away.
- Arm alarm when all-away and door locked.
- Disarm when someone changes to home.
- Notification when a family member leaves a work zone.

## Review before enabling

Event ordering and simultaneous source updates; unknown/unavailable inputs; stale evidence; restart recovery; bag semantics; mapping legacy entity IDs into new stable entities. Shadow mode must precede any live switch.

## Reviewed proposed change (not original YAML)

Per-person bag policy `always` enforces an all-day, persistent `away` guard whenever a configured bag reports `off`. This blocks false arrival from charging Watch + a neighbor's gate; it is checked before phone, Watch and entrance events. `unknown`/`unavailable` is not `off`. Mode `legacy` keeps the original YAML behavior. See [bag-policy.md](bag-policy.md) for scenarios, drawbacks and migration precautions.
