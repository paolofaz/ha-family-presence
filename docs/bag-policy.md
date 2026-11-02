# Bag absence priority — design decision

## Observed YAML failure

Legacy bag OFF moves a child to AWAY on weekdays 07:00–09:10. A Watch left charging at home may come back ON. If a gate, door opening or unlock happened recently (including a condominium neighbor's gate event), the Watch can wrongly move that person back to HOME. The original rules do not recheck whether the bag is still away.

## Per-person policy

- `always` (proposed default where a bag exists): confirmed bag OFF is a continuous AWAY invariant. The bag absence is re-evaluated **before every event**, including iPhone arrival, Watch ON, physical entry and startup reconciliation. This does not expire at 09:10 and sets AWAY even if bag removal is outside the old departure window.
- `legacy`: original YAML behavior, without bag veto; bag OFF moves AWAY only on weekdays 07:00–09:10 and bag ON moves HOME.
- Bag ON releases the absence veto and retains the original bag-arrival => HOME behavior.
- No configured bag: no precedence. `unknown`/`unavailable` MUST NOT be interpreted as OFF, and neither should itself produce arrival or departure events.
- The 07:00–09:10 window applies only to the legacy departure rule, not to the selected `always` policy.
- Additional scheduled policies may be added only after reviewing real scenarios; a school-hours window could reintroduce the false arrival after its cutoff.

**Safety trade-off:** a child can come home without their bag. Strict mode still reports AWAY; the resulting all-away state can influence an alarm YAML automation. An explicit auditable manual override with expiry, conflict diagnostics and sensor-off stability/debounce are required before activating strict mode for production. Do not silently grant priority back to Watch, phone or a shared gate.

## Example regression matrix

| Prior state | Incoming event | Bag state | Always policy | Legacy policy |
| --- | --- | --- | --- | --- |
| AWAY | Watch ON + recent shared gate | OFF | stays AWAY | HOME |
| AWAY | iPhone enters home | OFF | stays AWAY | HOME |
| NEAR_HOME | Door opens + Watch detected | OFF | AWAY | HOME |
| HOME | Bag OFF at 11:00 | OFF | AWAY | unchanged |
| AWAY | Bag ON | ON | HOME | HOME |
| AWAY | Watch ON + gate | UNKNOWN | HOME | HOME |
| HOME | Reconcile after restart | OFF | AWAY | unchanged |

## Adapter requirements (not yet implemented)

- Normalize current stable source state before calling the FSM; use a person-specific policy.
- Recheck bag after the Watch ON 2-second evaluation delay and immediately before committing a transition. A stale delayed Watch ON must not win over a newer bag OFF.
- Reject invalid/restore-only sensor events; real OFF must be confirmed, not a transient unavailable status.
- Serialize person-level processing and expose last rejected/blocked transition with an explanation.
- Compare outcomes against the existing YAML in shadow mode before switching any live alarm or home automations.
