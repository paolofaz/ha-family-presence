# Bag policy: priority is asymmetric

## Rules agreed for design

1. **Bag currently OFF ⇒ AWAY** in strict (`always`) mode, irrespective of phone, Watch, gate or door. This is a continuing guard, not merely a one-time departure event.
2. **Bag OFF → ON ⇒ HOME**: an actual, validated sensor transition confirms the arrival.
3. **Bag already ON ⇒ no precedence**: phone/Watch and existing FSM can change the person to AWAY. Bag presence does not continually force HOME.
4. **Bag UNKNOWN/UNAVAILABLE** must not be interpreted as OFF. A sensor recovering to OFF may re-apply the absence guard, but its recovery alone is not a new arrival.
5. `legacy` mode remains available per person, retaining weekday morning bag departures and allowing phone/Watch to override.

## Why

A Watch charging at home may turn ON during school hours. A neighbor opening a shared condominium gate shortly beforehand can then create a false HOME confirmation, even though the child's bag is still outside. The absent bag takes precedence over this indirect inference, at any time of day.

## Real trade-offs

A child may return without their bag; strict mode can therefore say AWAY while the child really is home. False bag OFF readings can produce the same problem. **Do not connect this experimental logic to alarm automations until bag debounce, diagnostic conflicts and a safe manual override are defined and tested.**

## Test matrix

| Earlier FSM | Event | Current bag | Strict output |
| --- | --- | --- | --- |
| AWAY | Watch ON + neighbor gate | OFF | remains AWAY |
| AWAY | iPhone enters home | OFF | remains AWAY |
| HOME | Bag goes OFF at 11:00 | OFF | AWAY |
| AWAY | Bag transitions OFF → ON | ON | HOME |
| HOME | iPhone leaves while bag already ON | ON | AWAY |
| HOME | Watch OFF with valid departure evidence, bag ON | ON | AWAY |
| HOME | Bag becomes UNKNOWN | UNKNOWN | no automatic arrival or departure |
| Unknown | Reconcile with stable bag OFF | OFF | AWAY |

The current coordinator evaluates the real bag state **after** any Watch ON delay and prevents a queued older Watch ON from overtaking a new bag/phone/Watch event. Live Home Assistant event-adapter integration tests and a manual-override design are still outstanding.
