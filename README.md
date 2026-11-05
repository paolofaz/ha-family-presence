# Family Presence

**A context-aware, event-driven family presence engine for Home Assistant.**

[![Latest release](https://img.shields.io/github/v/release/paolofaz/ha-family-presence?label=stable%20release)](https://github.com/paolofaz/ha-family-presence/releases/latest)
[![Validation](https://github.com/paolofaz/ha-family-presence/actions/workflows/validate.yml/badge.svg)](https://github.com/paolofaz/ha-family-presence/actions)
[![License: MIT](https://img.shields.io/github/license/paolofaz/ha-family-presence)](LICENSE)

Family Presence combines **phone location, Bluetooth wearables, optional backpack beacons, and shared entrance events** to determine whether each household member is **home**, **near home**, or **away**.

Instead of treating every device detection as proof that a person is home, it uses a **finite-state machine (FSM)** with explicit transition rules, time-limited evidence, and per-person state persistence.

It is designed for homes where people sometimes leave a phone or watch charging, children travel with a tracked school bag, Bluetooth reception is intermittent, and a shared door or gate can be operated by *any* household member.

> [!IMPORTANT]
> **Family Presence determines presence; it does not control your home.** It never arms or disarms an alarm, locks or unlocks doors, changes heating, or writes to legacy presence helpers. You choose what to automate using its Home Assistant entities.

**Current stable version:** [v1.0.2](https://github.com/paolofaz/ha-family-presence/releases/tag/v1.0.2) · **Type:** custom integration · **License:** MIT

## At a glance

- **Independent FSM per person:** `home`, `near_home`, and `away`.
- **Household-level output:** a binary sensor that is ON only when **everyone** is `away`.
- **Multiple evidence sources:** phone geofencing, Watch BLE, optional backpack BLE, doors, locks, gates, and optional alarm state.
- **Backpack-aware school trips:** configurable departure days and hours, with arrivals allowed at any time.
- **Protection against a watch left at home:** an accepted backpack departure cannot be overridden by the watch coming online or by someone else opening a shared entrance.
- **Manual corrections:** one-shot Home/Away buttons for every person, without permanently disabling normal detection.
- **Restarts and diagnostics:** saved FSM states, explanatory reasons, source warnings, access-event history, and privacy-conscious downloadable diagnostics.
- **UI configuration:** configure members, mappings, correlation windows, and backpack schedules without writing a presence engine in YAML.
- **Lightweight updates:** only relevant changes are published or persisted; there are no constantly updating elapsed-time sensors in this integration.

## How it works

Every person has an independent FSM. Input entities produce *events* (not continuous votes). The adapter validates actual transitions, the coordinator checks time windows and causal context, and the FSM decides whether a state should change.

```text
Phone location ─────────┐
Watch BLE presence ─────┤
Backpack BLE (optional) ┤
                        ├── Validated HA events ── Per-person FSM ── Presence sensors
Door / lock / gate ─────┤                                   │
Alarm state (optional) ─┘                                   └── All-away aggregate
                                                                  │
                                                       Your own HA automations
```

Shared entrances provide **corroborating evidence**, not a person's identity. A gate event by itself does not mean that a specific person arrived.

### The three states

| State | Meaning | Counts as a confirmed arrival? |
| --- | --- | --- |
| `home` | The FSM accepted evidence of being at home. | Yes |
| `near_home` | A Watch-related arrival is plausible but not yet confirmed. | **No** |
| `away` | The FSM accepted an absence/departure event. | No |
| Unknown / uninitialized | No usable stored state or accepted transition yet. | No |

`near_home` is **not a geographical zone**, and it is **not a fourth Home Assistant `person` state**. Its purpose is to avoid guessing between Home and Away when only provisional BLE evidence is available. There is **no automatic `near_home` expiration** in v1.0.1.

### The “house certainly empty” sensor

The aggregate binary sensor (displayed as **Casa certamente vuota** in the current release) is:

- **ON** only if **every configured member** is `away`.
- **OFF** if even one member is `home`, `near_home`, or not yet determined.

This is a strict **FSM-state aggregation**, not an independent physical occupancy measurement. A restored or manually forced `away` state also counts. If your automations depend on this aggregate, account for stale location data and what happens after a Home Assistant restart.

> [!WARNING]
> Do not disarm an alarm just because “house certainly empty” changes to OFF. A person entering `near_home` can turn the aggregate OFF **without a confirmed arrival**. For disarming, use a deliberate transition of a person's FSM to `home` and add the safety conditions appropriate to your alarm installation.

## Requirements and supported inputs

You need a working Home Assistant instance and **at least one personal presence source per member**. Family Presence consumes entities created by other integrations; it does **not** perform Bluetooth scanning or GPS tracking itself.

| Input | Home Assistant type | Required? | Used for |
| --- | --- | --- | --- |
| Phone location | `device_tracker` | Optional per person | Entering/leaving the `home` zone |
| Wearable BLE presence | `binary_sensor` | Optional per person | Watch detected / no longer detected |
| Backpack / bag BLE presence | `binary_sensor` | Optional per person | Scheduled departures and eligible returns |
| Gate or entrance pulse | `switch`, `binary_sensor`, or `lock` | Optional, shared | Time-correlated physical access evidence |
| Door contact | `binary_sensor` | Optional, shared | Door open / close events |
| Door lock | `lock` | Optional, shared | Lock / unlock events |
| Alarm panel | `alarm_control_panel` | Optional, shared | Extra evidence for a Watch departure |

You may configure a member with a phone only, a Watch only, a bag only, or a combination. **One person must not share a personal source entity with another person.** The configuration flow checks for duplicate personal sources and names.

**Recommended source setup**

- A Home Assistant Companion App phone tracker, or another tracker producing meaningful changes between `home` and an outside zone.
- A wearable BLE entity with genuine `on`/`off` transitions. The project [Watch BLE Presence](https://github.com/paolofaz/ha-watch-ble-presence) is one compatible source; for reliable Watch departure correlation, its binary sensor exposes `last_seen_before_off` when becoming OFF.
- An independently configured bag BLE presence binary sensor if backpack-based trips are useful in your household.
- Optional entrance sources that report *real state transitions*, rather than a static “gate currently open” assumption.

Phone tracking, BLE advertisements, receivers, timeouts, and geofences must be configured in their **source integrations**. Their reliability directly affects the quality of FSM decisions.

<!-- ha-marketplace:exclude-start -->

## Installation

### Home Assistant Marketplace (Home Assistant 2026.11 and later)

Starting with Home Assistant **2026.11**, the former HACS store is built into Home Assistant as **Settings → Marketplace**. The repository uses the same HACS-compatible packaging and catalog.

[![Open this repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=paolofaz&repository=ha-family-presence&category=integration)

1. Open **Settings → Marketplace**.
2. If Family Presence is not in the catalog, use **Add from link** (or the custom repository option) and provide `https://github.com/paolofaz/ha-family-presence` as an **Integration**.
3. Install the latest stable release.
4. Restart Home Assistant if requested.
5. Open **Settings → Devices & services → Add integration**, search for **Family Presence**, and start the setup wizard.

### HACS (Home Assistant versions before 2026.11)

1. Open **HACS** and use **⋮ → Custom repositories**.
2. Paste `https://github.com/paolofaz/ha-family-presence` and choose **Integration**.
3. Install **Family Presence**, restart Home Assistant, and add the integration under **Settings → Devices & services**.

**Custom repository installation is available without being listed in the public HACS / Marketplace catalog.** Catalog inclusion is a separate review and submission process.

### Manual installation

1. Download the [latest stable release](https://github.com/paolofaz/ha-family-presence/releases/latest).
2. Extract `family_presence.zip` so its files are located directly under:

   ```text
   /config/custom_components/family_presence/
     __init__.py
     manifest.json
     config_flow.py
     ...
   ```

   The ZIP is **flat**: do not add an extra nested `family_presence` directory.

3. Restart Home Assistant.
4. Add **Family Presence** from **Settings → Devices & services**.

Do not copy the entire GitHub repository into `custom_components`. Install the release asset or the contents of `custom_components/family_presence/`.

<!-- ha-marketplace:exclude-end -->

## First-time configuration

Family Presence currently supports **one household configuration entry** with any number of members (at least one). Each member requires at least one personal input.

### 1. Create the household

Under **Settings → Devices & services → Add integration → Family Presence**:

1. Set the **household name** (the default is `Home`).
2. Optionally select **gate events**, a **door contact**, a **door lock**, and an **alarm panel**.
3. Continue to the person setup.

The entrance and alarm inputs belong to the whole household. A gate or door event may be relevant to multiple people, so the FSM will never treat it as independently identifying who entered.

### 2. Add household members

For each person:

1. Enter a distinct display name.
2. Select one or more personal sources: **phone**, **Watch/wearable BLE**, **backpack BLE**.
3. Choose **Add another person** as needed.
4. Finish setup.

The integration creates a single virtual household device containing its output entities. You do **not** need to create `input_select` or `input_text` helpers for the FSM.

### 3. Tune behavior with Configure

On the Family Presence entry, open **Configure** to change:

- **Event correlation windows**, in seconds.
- **Backpack departure schedules**, separately for each person with a bag sensor.

Use **Reconfigure** instead to change the household's shared inputs, edit source mappings, rename someone, or add/remove members. Reconfigure preserves the stable identity of existing members where applicable.

The Watch's BLE polling interval and presence timeout, and the bag sensor's detection timeout, are **not** Family Presence options. Change those in the integrations that provide the BLE sensors.

## Event correlation windows

Physical events help corroborate a Watch's arrival or departure. The defaults are:

| Option | Default | Meaning |
| --- | ---: | --- |
| `exit_gate_seconds` | 120 s | Recent gate event for Watch departure |
| `exit_door_seconds` | 90 s | Recent door closing for Watch departure |
| `exit_lock_seconds` | 90 s | Recent locking for Watch departure |
| `entry_gate_seconds` | 120 s | Recent gate event when Watch appears |
| `entry_door_seconds` | 120 s | Recent door opening when Watch appears |
| `entry_lock_seconds` | 120 s | Recent unlocking when Watch appears |
| `near_home_entry_seconds` | 180 s | Maximum age of a *new* Watch-triggered `near_home` observation when a subsequent shared entrance may confirm `home` |

The configurable windows accept **1–3600 seconds**. A newly detected Watch is additionally checked after a short **2-second delay** so an immediately stale BLE reading is not accepted.

The `near_home_entry_seconds` limit prevents a door opened hours later from confirming an old provisional arrival. **It does not itself return `near_home` to `away`.**

For Watch departures, Family Presence correlates door/gate/lock timestamps against **`last_seen_before_off`**, when supplied by the Watch's binary sensor, rather than assuming the moment the timeout generated OFF was the last moment the Watch was near home.

**Important:** configuring a `lock` as a gate source accepts an unlock transition as a *control event*. It is **not proof that the gate physically opened**. Prefer a genuine pulse/contact source if your hardware makes one available.

## Understanding the decision rules

Family Presence is **event-driven**. A source sitting at `home` or `on` is not repeatedly interpreted as a new arrival. Valid state changes are what matter.

### Phone: geofence entry and exit

| Accepted phone transition | FSM result |
| --- | --- |
| `home` → outside zone (for example `not_home` or a named zone) | `away` |
| Outside zone → `home` | `home` |
| `unknown` / `unavailable` → `home` | Ignored as a new arrival |
| `home` → `unknown` / `unavailable` | Ignored as a new departure |
| `home` → `home` | No event |

A named outside zone such as Work or School is **not** an extra FSM state. Use Home Assistant's `person` entity or a separate display template for geographical labels.

A tracker that genuinely produces `not_home → home` will be interpreted as an arrival. If a source falsely emits those transitions during power cycling or reconnection, Family Presence cannot establish physical movement from the state name alone. Configure and test your phone tracker accordingly.

### Watch / wearable: provisional arrival

- On a genuine `off → on` transition from `away`, a Watch can indicate `near_home`.
- If an accepted physical entrance event was already recent, the Watch may confirm `home` directly.
- An entrance event occurring **after** `near_home` can confirm `home` only while the Watch remains ON and the original Watch observation is no older than the configured `near_home_entry_seconds`.
- A `on → off` transition from `near_home` returns to `away`.
- From `home`, Watch OFF requires appropriate departure evidence: for example a phone outside, recent correlated gate/door-close/lock event, or an armed-away alarm.
- When a **valid backpack departure is still authoritative**, a Watch left charging at home cannot cause `away → near_home` or `away → home`, even together with a shared door/gate event (v1.0.1 safeguard).

An intermittent BLE signal alone is not proof that a person entered or left. The integration intentionally avoids synthetic events on source recovery from `unknown` or `unavailable`.

### Backpacks: a departure with causal provenance

A bag sensor reports `on` when present and `off` when absent.

**Departure: `on → off`**

A bag departure can set its owner to `away` when:

1. The bag feature is enabled for that person.
2. The actual accepted OFF event occurs on a configured day and inside the configured departure time window.
3. The person is not already `away`.

If the bag event **actually caused** the move to `away`, the FSM records `bag_return_eligible = true`. This flag records **why the person became away**; it is not simply a mirror of the bag's current BLE reading.

**Return: `off → on`**

A real bag return may set the person to `home` **at any time of day** when:

- The bag is enabled.
- The current FSM state is `away` or `near_home`.
- `bag_return_eligible` is still `true`.
- The event is a valid new `off → on` transition, not merely a restored `unavailable → on` reading.

The flag is consumed when a return is accepted. An unrelated iPhone departure, manual correction, or other authoritative event can replace the original cause and revoke the bag's return eligibility.

**v1.0.1 precedence:** While the accepted bag-caused absence remains active, a Watch left at home and a shared entrance cannot falsely confirm the owner has arrived. A genuine later **phone zone-entry event**, or an explicit manual Home command, can still establish a return without the bag.

**Not a permanent bag veto:** An absent bag with `bag_return_eligible = false` does *not* block the usual phone/Watch logic. A bag departing after an iPhone has **already** established `away` does not retroactively become the departure's owner; this avoids giving an unrelated reconnection authority to confirm a return.

### Backpack schedule examples

The default is **Monday–Friday, 07:00–09:10**, interpreted in the Home Assistant local time zone.

| Configured window | Behavior |
| --- | --- |
| Weekdays 08:00–09:00 | An accepted bag OFF at 08:20 can mark Away; a later valid ON can mark Home at 13:30 |
| Every day 00:00–00:00 | All-day departure window |
| Monday 22:00–02:00 | Also includes Tuesday before 02:00 |
| Disabled | Bag events are ignored; other configured sources still work |

The schedule applies to the **accepted departure event timestamp**. It does **not** re-evaluate when a Watch powers on, and it does **not** limit what time an eligible bag may return.

Bluetooth detection has a timeout, so an OFF event can occur later than the physical moment the bag left radio range. Take that delay into account near the beginning or end of the departure window.

### Real-world examples

| Situation | Expected outcome |
| --- | --- |
| A child leaves with a school bag, leaving Watch and phone at home | Accepted bag departure → `away`, with bag return eligible |
| The Watch left charging at home comes online an hour later | Remains `away`; no false `near_home` |
| A different household member opens the shared front door | Cannot override that still-authoritative bag departure |
| The child returns with the bag in the afternoon | Eligible bag `off → on` → `home`, regardless of school departure hours |
| The child returns without the bag but carries an iPhone that genuinely enters the Home zone | Phone entry → `home` |
| A phone reappears as `home` from `unavailable` after being powered back on | No fabricated arrival |
| A Watch returns while no authoritative bag trip exists | `near_home`, or `home` with accepted timely physical corroboration |
| Someone uses Force Away | `away` immediately; this manual action does not authorize a bag-only return |

These are **logic examples**, not a guarantee about how each Bluetooth or GPS provider reports real hardware movement.

## Entities created

Entity display names in v1.0.2 include some **Italian labels** retained for compatibility with existing installations. Actual `entity_id` values are assigned by Home Assistant and can vary by household name, prior registry entries, or manual renaming. **Never copy an assumed entity ID into an alarm automation without checking it.**

| Entity | One per | Purpose |
| --- | --- | --- |
| **Presenza [name]** (sensor) | Member | Current FSM state: `home`, `near_home`, `away` |
| **Casa certamente vuota** (binary sensor) | Household | ON iff everyone is `away` |
| **Diagnostica presenza** (sensor) | Household | Aggregate diagnostic status and relevant warnings |
| **[Name] — Forza a casa** (button) | Member | One-shot manual `home` correction |
| **[Name] — Forza fuori casa** (button) | Member | One-shot manual `away` correction |
| **Ultimi eventi accessi** (diagnostic sensor) | Household, if shared access sources are configured | Last observed gate, door, and lock events |

### Personal sensor attributes

Each person sensor exposes:

| Attribute | Meaning |
| --- | --- |
| `reason` | Human-readable explanation of the last accepted FSM decision |
| `last_transition` | Timestamp of the most recent state transition (or applicable manual correction / policy migration) |
| `bag_return_eligible` | For configured bags only: whether the current eligible trip can be resolved by a genuine bag return |

`bag_return_eligible: false` is **not** a Bluetooth error. It means the bag is not currently authorized to confirm Home by itself.

### Household diagnostic sensor

Its state is one of:

- `all_away` — everyone is `away`;
- `presence_indicated` — at least one member is `home` or `near_home`;
- `incomplete` — the configured member states do not establish either of the above.

In its attributes you may see:

- `source_warnings`: per-person observations such as unavailable sources or unexpected combinations;
- `restored_unverified_members`: members whose saved state has not yet been refreshed by a newly accepted event.

A restored/unverified state is **informational**, not automatically an anomaly. Similarly, a phone or Watch left at home during a recognized backpack trip can be normal; v1.0.1 suppresses those expected contradictions when the person is `away`, the accepted bag-trip flag is active, and the bag remains OFF.

### Access history is for display, not decisions

If gate, door, or lock sources are configured, a separate **Ultimi eventi accessi** sensor summarizes their latest valid events. Attributes may include:

- `cancelli` (per-gate timestamps);
- `porta_aperta` / `porta_chiusa`;
- `serratura_sbloccata` / `serratura_bloccata`;
- `ultimo_evento_alle` / `ultima_sorgente`.

Those timestamps are saved separately for **dashboard history**. On restart, they are **never replayed as fresh evidence** to make the FSM change state.

## Manual controls

Every household member gets two Home Assistant `button` entities:

- **Force Home**: set `home` immediately.
- **Force Away**: set `away` immediately.

This is a **single FSM event, not a permanent override**. A subsequent valid source event can change that state again. Manual Away intentionally does not grant the backpack permission to confirm an unrelated return.

For a dashboard, use the standard **Entities** card with a **buttons** row. The example below is intentionally generic: replace both placeholder IDs with the real button entities from your installation.

```yaml
type: entities
title: Manual presence controls
show_header_toggle: false
entities:
  - type: section
    label: Example member
  - type: buttons
    entities:
      - entity: button.REPLACE_WITH_FORCE_HOME
        name: Home
        icon: mdi:home-import-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.REPLACE_WITH_FORCE_HOME
          confirmation:
            text: Confirm forcing this member HOME?
      - entity: button.REPLACE_WITH_FORCE_AWAY
        name: Away
        icon: mdi:home-export-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.REPLACE_WITH_FORCE_AWAY
          confirmation:
            text: Confirm forcing this member AWAY?
```

Confirmations are strongly recommended if the presence outputs feed alarm automations.

## Using Family Presence in automations

Family Presence exposes **read-only results and explicit correction buttons**. External automations remain responsible for **alarms, locks, heating, lights, and notifications**.

A safe conceptual split is:

- **Arm-away candidate:** the all-away binary sensor changes to ON, *and* your own safety conditions (for example verified lock state and an unarmed alarm) are satisfied.
- **Disarm candidate:** an actual per-person FSM transition from `away` or `near_home` to **`home`**, with your own alarm-state and authorization conditions.
- **Never disarm solely on:** a Watch becoming detectable, a shared gate opening, or the all-away aggregate turning OFF because of `near_home`.

Here is an **illustrative** Home Assistant automation. Replace the placeholder entity IDs and thoroughly test the behavior **before** connecting it to an active security system:

```yaml
alias: Example - arm only when the household is away and the door is locked
triggers:
  - trigger: state
    entity_id: binary_sensor.REPLACE_WITH_ALL_AWAY
    to: "on"
conditions:
  - condition: state
    entity_id: lock.REPLACE_WITH_FRONT_DOOR
    state: "locked"
  - condition: state
    entity_id: alarm_control_panel.REPLACE_WITH_ALARM
    state: "disarmed"
actions:
  - action: alarm_control_panel.alarm_arm_away
    target:
      entity_id: alarm_control_panel.REPLACE_WITH_ALARM
mode: single
```

This is **not** installed or activated by Family Presence. It is an example of how to consume the aggregate, not a complete safety policy for every home. In particular, understand the effect of manual Away and restored Away states before enabling alarm actions.

You can display work/school locations separately using `person` entities or Home Assistant template sensors. The FSM itself deliberately keeps only its three logical states.

## Restarts, recovery, and persistent state

Family Presence saves accepted FSM decisions in Home Assistant storage and restores them after a restart. It also saves access-event history separately. Manual corrections and causal backpack eligibility are part of the state snapshot.

**What a restart does not do:**

- It does not pretend that a phone already showing `home` has just arrived.
- It does not treat `unknown`/`unavailable` → valid as a fresh physical transition.
- It does not replay old entrance timestamps into the short-lived correlation windows.
- It does not synthesize a missing trip that occurred while Home Assistant was offline.

A restored state can be operationally authoritative while still marked **unverified** in diagnostics until a new accepted event occurs. An all-away household restored entirely as Away can therefore still make the aggregate ON.

**v1.0.1 legacy-state correction:** if a snapshot contains `near_home` with `bag_return_eligible: true`, and the bag is **currently confirmed OFF**, the restored state is normalized to `away` while preserving the bag return right. If the bag is ON or unavailable, `near_home` is preserved rather than guessing a new absence.

> [!WARNING]
> That startup correction can change the household all-away aggregate and affect **your external alarm automation**. Check real occupancy and temporarily disable automatic arming during the first upgrade/restart if your installation requires it.

If a member actually returned while Home Assistant was offline, the saved `away` state can be stale. Wait for a genuine new source event, review diagnostics, or use Force Home after verifying occupancy. **Do not delete and recreate the integration to solve a stale presence state.**

### Upgrading from earlier releases

- **From v1.0.0:** update normally through Marketplace/HACS (or the release ZIP), then restart if required. No config-entry recreation is needed.
- **From Beta/RC releases:** update in place. Existing member identities, entity-registry unique IDs, and compatible stored states are preserved by the migration logic.
- Some historical `entity_id` values may still contain `shadow` after upgrading. That is a registry naming detail, **not** an indication that the live integration is running in shadow mode. Review dashboard and automation references before renaming entities.

For the specific v1.0.1 correction, see [its release notes](docs/v1.0.1-release-it.md). The [v1.0.2 release](docs/v1.0.2-release-en.md) contains **no additional FSM behavior changes**.

## Diagnostics, logging, and privacy

### Download a diagnostic report

In **Settings → Devices & services → Family Presence**, open the integration's diagnostics download action (where available in your Home Assistant UI).

The report is generated **on demand** and includes the FSM state, causal bag flag, last decision, recent accepted/ignored events (up to 12 per person), source availability, correlation settings, and summarized access history.

To reduce exposure, the report excludes **member names, source entity IDs, exact GPS coordinates, zone names, and BLE addresses**. It still contains **event timestamps** and household behavior metadata. Review it before sharing publicly.

### Log and storage behavior

- Personal outputs are published when their visible state or attributes actually change.
- Ignored events do not generate continuously changing counters on production member sensors.
- FSM persistence is scheduled for **accepted decisions** and on unloading, rather than after every irrelevant BLE update.
- Entrance history has its **own storage**, separate from the ephemeral physical evidence used by the FSM.
- Family Presence does not expose a live “seconds since last event” counter that writes to Recorder each second.

Internal ignored-event diagnostics are not guaranteed to survive an abrupt crash if there was no later accepted decision that triggered persistence.

### Security and data boundaries

- The integration reads configured Home Assistant states and creates presence/diagnostic entities.
- It does **not** connect to Watches, perform Bluetooth scans, track GPS itself, or call external cloud APIs.
- It does **not** obtain or store Watch IRKs; those belong to the independent BLE provider.
- It does **not** invoke alarm, lock, gate, heating, or other actuator services.
- As with any presence system based on wireless signals and geofencing, **false positives and stale states remain possible**. Avoid treating a single FSM state as a guarantee of physical safety.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No member sensors appear after installation | Confirm the integration was added under Devices & services after copying the files; check the HA logs and actual entity registry |
| A member has no state after initial setup | A new FSM needs a valid accepted event, or an existing compatible snapshot to restore |
| The name or entity ID looks Italian or contains `shadow` | Display names preserve existing installation compatibility; check the actual entity registry rather than guessing IDs |
| A Watch appears ON but its owner remains Away | Expected if an accepted backpack trip remains active; inspect `bag_return_eligible` and the bag sensor |
| A member remains Near Home indefinitely | `near_home` has no automatic expiration; check for a real phone arrival, eligible bag arrival, Watch OFF, or a valid timely entrance |
| The backpack left but did not set Away | Verify an actual `on → off` transition, the configured local day/time window, and whether the member was already Away |
| Backpack returned but did not set Home | Check `bag_return_eligible`, bag enabled, and whether the source actually changed `off → on` rather than recovering from `unavailable` |
| Source reads `unavailable` after reboot | Recovery is deliberately not interpreted as a new trip; inspect the source integration and diagnostics |
| “Restored unverified” appears | Informational after a restart; the stored state has not yet been corroborated by a new accepted event |
| A shared door event did not confirm Near Home | The Watch must still be ON, the original Near Home detection must be recent enough, and no authoritative backpack trip may block it |
| An automation does not trigger as expected | Check real `entity_id` values, each person's state transition, and whether the aggregate actually went ON or OFF |
| The alarm behavior is unexpected | Disable the relevant external automation while investigating; Family Presence itself never commands the alarm |

When reporting a reproducible problem, include the **integration version**, the input states *before and after* the event, the member FSM state and `reason`, and a sanitized diagnostics report. Never publish sensitive Bluetooth keys, raw home addresses, or other private data.

[Open an issue](https://github.com/paolofaz/ha-family-presence/issues/new)

## Design principles and known limitations

Family Presence is deliberately **not** a generic occupancy confidence-score engine:

1. **Events, not votes.** It responds to validated source changes; it does not continuously recalculate a probability from currently visible entities.
2. **Causal provenance matters.** A valid backpack-caused Away must not be cancelled by a Watch left on a charger.
3. **Unknown is not movement.** Source recovery and bootstrap values cannot manufacture entries/exits.
4. **Shared events are shared.** Gate, door, and lock signals cannot prove which member acted; the correlation windows reduce but do not eliminate ambiguous matches.
5. **Provisional is not confirmed.** `near_home` never means `home` for disarming decisions.
6. **No autonomous repair of stale states.** The FSM cannot reconstruct events missed during a Home Assistant outage; manual corrections are available.
7. **No actuator side effects.** Alarm and household controls are always owned by separate user automations.

In particular, a real phone `not_home → home` transition can establish Home even with an absent bag. The integration trusts that accepted tracker transition; if a provider fabricates it during reconnection, the source should be fixed or filtered. Also, if a phone has *already* established Away, a later bag departure does not take over the reason retroactively.

These trade-offs are intentional. The objective is an **understandable, testable presence decision**, not a claim of infallible identification.

## Architecture and development

```text
custom_components/family_presence/
├── config_flow.py       UI setup, reconfigure, and options
├── sources.py           Home Assistant event adapter
├── coordinator.py       Per-person runtime, evidence, and persistence snapshot
├── fsm.py               Pure state-transition decisions
├── bag_schedule.py      Time/day rules for accepted bag departures
├── readiness.py         Household aggregate assessment and source warnings
├── sensor.py            Person, diagnostic, and access-history sensors
├── binary_sensor.py     Household all-away output
├── button.py            One-shot manual controls
├── access_history.py    Separate display-only entrance history
└── diagnostics.py       Downloadable Home Assistant diagnostics
```

Source code is organized to keep FSM decisions independent of Home Assistant service calls. Tests cover transition rules, backpack causality, snapshot compatibility, event ordering, entity behavior, source filtering, and packaging.

**Latest validated stable code:** v1.0.2 · **226 automated unit tests** at the stable release, plus HACS validation and Home Assistant hassfest.

To run the unit tests from the repository root:

```bash
python -m unittest discover -s tests -v
python -m compileall -q custom_components tests
```

Additional documentation:

- [Architecture](docs/architecture.md)
- [Backpack rules and precedence](docs/bag-policy.md)
- [v1.0.2 release notes](docs/v1.0.2-release-en.md)
- [v1.0.1 release notes](docs/v1.0.1-release-it.md)
- [v1.0.0 original stable release](docs/v1.0.0-release-it.md)
- [All releases](https://github.com/paolofaz/ha-family-presence/releases)

## Contributing and support

Bug reports and reproducible field scenarios are welcome through [GitHub Issues](https://github.com/paolofaz/ha-family-presence/issues). Before proposing a behavioral change, describe the expected state, the source transition, and the effect on the all-away aggregate; new rules should not introduce false Home confirmations or unsafe alarm assumptions.

This is a **community-maintained custom integration**, not an official Home Assistant core integration. It is installable from its public repository; inclusion in the default Marketplace/HACS catalog requires separate submission and review.

For repository authors, see the official [Marketplace catalog submission guide](https://contributors.home-assistant.io/marketplace/guides/catalog/).

## 🍺 Support the Project

If you found this project useful and want to support my work, you can offer me a beer:

[![Buy Me a Beer](https://img.shields.io/badge/Buy%20Me%20a%20Beer-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/PaoloFazari)



## License

Distributed under the [MIT License](LICENSE).

**Family Presence** is an independent community project and is not affiliated with, endorsed by, or supported by Home Assistant, Apple, or the maintainers of third-party source integrations.
