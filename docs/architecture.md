# Architecture and implementation roadmap

## Component separation

Input entities (phone / BLE / gate / door / lock / bag / alarm)
-> HA event adapter [not implemented]
-> normalized evidence and validated timestamps [not implemented]
-> pure deterministic decide() in fsm.py [implemented baseline]
-> per-person serialized runtime with persistent state [not implemented]
-> HA state sensors, all-away binary sensor and diagnostics [not implemented]
-> downstream YAML actions (alarm, notifications, lights).

There must be **one writer** of each FSM state. The FSM must never issue actuator commands itself.

## Configuration

One household configuration entry; number of people is not hard-coded. Shared entrance sensors and each person's phone / wearable / bag sources are chosen through entity selectors. Time windows default to legacy values: departure gate=120, door=90, lock=90 seconds; arrival gate=120, door=120, unlock=120 seconds. Other policies (bag time window, 2s Watch delay) are left untouched until review.

The wizard is a first-stage scaffold; entity update / reconfiguration UX and event adapters are still required.

## Guardrails before migration

1. Review the reported bag edge case, without silently changing the existing policy.
2. Specify priority and event ordering when phone, watch and bag disagree.
3. Reject unknown/unavailable and startup restoration as arrival or departure evidence.
4. Persist state and event metadata reliably across restarts.
5. Add shadow-mode logging and test current versus candidate transitions.
6. Expose stable entities, and only then migrate consumers away from the existing input_select helpers.
7. Keep independent notification and alarm automations separate from the decision engine.

## HACS-readiness, not publication

The one-integration layout, manifest version, metadata, i18n and CI conventions follow custom integration expectations. A Home Assistant Brands entry and green HACS/hassfest checks are required for future public catalog submission; this repository is not HACS-published yet.
