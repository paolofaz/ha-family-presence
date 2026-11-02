# Configuration philosophy: a bounded policy surface

**Decision:** keep the deterministic FSM in Python and expose only parameters with a clearly defined safety and UX purpose. We deliberately do not support arbitrary rule expressions, editable priorities, or a universal automation editor.

## Fixed, tested engine

- State model `home`, `away`, `near_home`.
- Transition and evidence rules: when phone/Watch/physical/bag changes can move a person.
- One serialized state writer per person and explicit unknown/unavailable handling.
- Asymmetric bag semantics: confirmed bag absent can force away; actual off→on arrival confirms home; a bag simply being present **does not** keep a person home.
- Watch ON evaluation delay of two seconds, currently fixed until evidence justifies tuning.
- Conservative all-away semantics; no actuator calls from the integration.

## Configurable per household

- Person mappings to phone tracker, Watch/BLE binary sensor, optional bag binary sensor, optional legacy helper. These are editable in **Reconfigure** without removing the entry. Users can also add/remove members; removing the last member is forbidden. Personal source entities cannot be shared between members.
- Shared gate, door, lock and alarm entities, modified with the integration entry's **Reconfigure** action.
- Six physical-event correlation time windows in **seconds** with original YAML defaults. Adjusted via Configure → Event correlation windows.
- No Bluetooth scan or absence timeout settings: these belong to Beacon BLE Presence, Watch BLE Presence, or an alternative entity provider.

## Configurable per person

Only **backpack precedence** is exposed as an explicit behavioral policy, and only for a person who has a configured bag:

| Policy | Semantics |
| --- | --- |
| `always` (default) | If the current bag is definitively off, person must be away. A real off→on transition sets home; bag already on is not a home lock. |
| `legacy` | Matches the previous YAML: bag on sets home; bag off sets away only in the weekday 07:00–09:10 local window, and other sources can override. |

Go to **Configure → Backpack priority → choose person → choose policy**. A policy change is stored in `entry.options["bag_policies"][person_id]`, without altering person source identifiers. `OptionsFlowWithReload` reloads the shadow integration so it becomes active. Previous early config entries without `person_id` use a normalized name key for compatibility.

## Configure versus Reconfigure (Home Assistant UI)

**Configure** changes policy/settings (`entry.options`): six correlation windows and per-person bag precedence. **Reconfigure** changes setup data (`entry.data`): household name/common physical entities and the set of people and their source entity mappings. Reconfigure uses the existing entry's unique ID and reloads it; it never creates a second entry or edits YAML.

New members receive stable IDs independent of their names. For early name-based entries, the first edit freezes the original normalized key into `person_id` to prevent a rename from changing entity identity. Source remapping invalidates stale shadow snapshots via the per-person fingerprint and reseeds from valid legacy YAML reference states when available.

## Deliberately not configurable yet

- `near_home` automatic timeout: could incorrectly contribute to all-away and arm an alarm, so shadow diagnostics are collected first.
- A school-hours bag veto: would allow false Watch arrivals after the cutoff; add only with evidence.
- Further bag-OFF debounce: the dedicated provider already waits 180 seconds after last advertisement; adding a second delay could double absence latency.
- Arbitrary conditions, priorities, scripts or template actions: opaque and difficult to test.
- Manual overrides and production all-away outputs: still need explicit alarm-safe design and tests before activation.

All changes remain shadow-only until Home Assistant runtime and safety scenarios have been verified.
