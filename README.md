# Family Presence for Home Assistant

Multi-person presence detection for Home Assistant based on a finite state machine (FSM) and multiple evidence sources: phone zone tracking, BLE wearable presence, entrance events and optional bag sensors.

> **Development foundation (0.1.0a1) — not ready to replace your existing automations.** The configuration UI records source mappings and time windows, and a pure-Python FSM is covered by regression tests. Home Assistant event listeners, state entities, alarm effects and persistent state are **not yet connected**. No working home presence or alarm YAML should be disabled at this stage.

## Design goals

- Preserve the three existing states: home, near_home, away.
- One independent FSM per member and one household all-away result.
- Parameterize member count, BLE/phone/bag source entities and shared gate/door/lock/alarm sources.
- Preserve legacy rules except for explicitly reviewed configurable bag absence priority.
- Isolate event-to-decision logic from Home Assistant adapters and persistence.
- Keep downstream automation actions (alarm, lights, notifications) in YAML.
- Validate new results in shadow mode against the running YAML implementation before migration.

## Repository layout

- custom_components/family_presence/: HACS-standard integration directory (manifest, config flow, FSM, translations).
- docs/baseline.md: baseline rules extracted from current YAML.
- docs/architecture.md: interfaces, migration boundaries and roadmap.
- docs/bag-policy.md: persistent bag-absence priority, hazards and regression scenarios.
- tests/: self-contained unit tests for the pure FSM.
- hacs.json: HACS repository metadata.
- .github/workflows/validate.yml: unit tests, HACS validation and hassfest.

## Configuration status

The UI wizard allows one household, optional shared entrance entities and as many people as needed. Each person can select a phone tracker, a BLE wearable sensor and/or a bag sensor. Defaults for correlation windows preserve the legacy package: exit gate 120s, door close 90s, lock 90s; entry gate/door open/unlock 120s. The proposed **always** bag policy (default for a configured bag) forces away whenever its sensor is validly OFF, at any time, and overrides phone/Watch/shared entrance evidence. **legacy** mode retains the original school-morning departure rule and allows other signals to override it. Policies are configured per person; they are not active in Home Assistant until the runtime is implemented.

**These UI options are saved but do not drive presence yet.** Member mappings cannot yet be edited through Options; that will be completed before a production release.

## Development checks

Run: python -m unittest discover -s tests -v

This repository is structured as a future HACS custom integration. Passing HACS checks and being listed in the HACS default catalog are separate milestones; branding, runtime behavior and release testing remain to be completed.

The working legacy YAML package is intentionally not included in this public repository, to avoid publishing household-specific names and entity IDs.

License: MIT.
