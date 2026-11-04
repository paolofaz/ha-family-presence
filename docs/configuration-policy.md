# Configuration philosophy — limited, understandable parameters

The Python FSM owns the state transition rules. The user configures sensor
mappings and **when a bag departure event matters**, never arbitrary rules,
priority expressions, or a generic automations editor.

## Per household

Phone/Watch/beacon entity mappings and shared gate, door, lock and alarm entity
mappings; six evidence correlation windows (existing YAML defaults); unlimited
number of members, each with a stable identifier. Source remapping and member
changes use **Reconfigure**. Evidence-window settings use **Configure**.

BLE absence/presence timing stays in the independent Watch/Beacon integrations.

## Per person: one backpack schedule, not two policies

In **Configure → Backpack schedule → person**, choose:
- Enabled (false ignores the bag completely)
- Start time and end time (equal means 24 hours)
- Selected weekdays (0 Monday through 6 Sunday)

Bag ON→OFF during that window sets AWAY **once**. Bag OFF→ON sets HOME any
time while enabled. All other valid sensor events subsequently work normally.
An overnight window may cross midnight. New members default to weekdays
07:00–09:10. Prior Alpha `always` migrates to full-day, `legacy` to school
hours, without retaining a separate behavior mode.

## Manual state input

Every member exposes two diagnostic-only buttons:
**Forza a casa** and **Forza fuori casa**. Each is a one-time state event,
not a lock, a hold or a manual-exception timeout. The next new iPhone, Watch
or bag state-change event can update the state.

## Not configurable / not production yet

Core FSM, evidence ordering, invalid-source filtering, conservative all-away,
and source-delay handling remain tested code. There is no automatic
near-home timeout or permanent backpack veto. All manual buttons and shadow
presence entities are isolated from production alarm automations.

The earlier decision issue about `always` versus `legacy` is **resolved by
this single schedule model**; there is no two-mode choice to revisit for
the final release. Only real-world field behavior and safety remain to verify.
