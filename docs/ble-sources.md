# BLE source integrations — source contract and timing review

Reviewed on 2026-11-02 using the `main` branches of:
- [paolofaz/beacon-ble-presence](https://github.com/paolofaz/beacon-ble-presence)
- [paolofaz/watch-ble-presence](https://github.com/paolofaz/watch-ble-presence)

The user's configured values were supplied in conversation; **the live Home Assistant configuration UI was not accessed**. The home-assistant-hosted `/config/integrations/integration/watch_ble_presence` URL is an instance-local UI route, not a public source code link.

## Beacon BLE Presence (backpacks)

Files reviewed: `coordinator.py`, `const.py`, `binary_sensor.py`, `parser.py`, README and tests.

- Matches one beacon by iBeacon UUID + Major + Minor, using Home Assistant's Bluetooth scanner/proxy infrastructure; does not scan independently.
- The **user-configured timeout is 180 seconds**. The integration makes a beacon `off` once the most recent valid BLE advertisement is at least 180 seconds old, during a periodic refresh.
- **Actual code**: `REFRESH_INTERVAL_SECONDS = 15` in `const.py`. Current README claims a 5-second check: **documentation discrepancy**, not assumed runtime behavior. Periodic transitions can lag the precise timeout boundary by up to roughly one check interval, subject to HA scheduling.
- A new matching advertisement can set `on` immediately in the Bluetooth callback, or in periodic cache processing (including the mechanism for duplicate-suppressed advertisements).
- On HA integration startup, `present=None` means unavailable. Old cached packets cannot declare it ON. If no post-start advertisement arrives, the first OFF state is determined after 180 seconds. Thus `unavailable → off` is *not* a physical bag departure.
- Real `on → off` indicates loss of packets over the timeout, not proof a child physically left. Real `off → on` means a verified advertisement was received, not cryptographically authenticated identity.
- The public binary sensor currently implements only `available` and `is_on`. The coordinator stores `last_seen` and `last_source` internally, but the inspected `binary_sensor.py` does **not currently publish them as attributes**, despite README wording. Family Presence should rely on the public binary sensor for now.

## Watch BLE Presence (wearables)

Files reviewed: `coordinator.py`, `ble_resolver.py`, `binary_sensor.py`, `sensor.py`, `config_flow.py`, README and tests.

- Uses Watch-specific IRKs to resolve rotating private BLE addresses from Home Assistant's cached advertisements. It does not run BLE scans itself. The sensitive IRKs stay in this integration's config entry; Family Presence must **never request, read, duplicate or store them**.
- **User configured:** update interval 15 seconds; presence timeout 180 seconds. The former is **polling frequency**, *not* a 15-second ON confirmation/debounce. At an update, a Watch is ON if the freshest relevant packet is no older than 180 seconds.
- OFF is decided on a poll when the last packet's age exceeds 180 seconds. Detection may lag until the next polling cycle and general HA scheduling.
- On OFF, the binary sensor publishes `last_seen_before_off` as an ISO 8601 timestamp, taken from the actual freshest packet and **not** the time of the OFF state transition. The source also exposes last-seen time, age, scanner, address, RSSI and name as separate sensors.
- Family Presence must keep using `last_seen_before_off` for its existing physical exit windows (gate 120s, door close 90s, lock 90s). Do not correlate against receipt of Watch OFF, roughly 3 minutes later.
- The Watch coordinator can use fresh-enough preexisting cache entries at startup; unlike Beacon BLE Presence it does not explicitly reject packets observed before its own startup. This is a meaningful implementation difference. Our source adapter ignores `unknown/unavailable → on` as a genuine arrival, avoiding synthetic Watch entry events in shadow mode.

## End-to-end effect on Family Presence

| Source event | Typical timing from physical BLE disappearance | Family Presence interpretation |
| --- | --- | --- |
| Bag last advertisement | t=0 | Bag may still be ON |
| Bag OFF from provider | ~180s + refresh/scheduling | **NOW** strict bag veto activates: `away` |
| Watch OFF from provider | ~180s + poll/scheduling | Watch departure path evaluated, using last_seen_before_off |
| Watch ON from new advertisement | Next 15s poll (possibly sooner/later depending cadence) | Existing 2s Family Presence confirmation delay; re-read bag and source before final decision |
| Bag OFF→ON | Immediately on matching Bluetooth callback, or cache refresh | `home` on a genuine validated off→on transition; bag remaining ON does not lock HOME |

The two 180-second source timeouts are **independent**, and time delays are approximate rather than guaranteed precise deadlines. BLE presence is probabilistic and does not, by itself, establish that the person carrying the device is home.

**Design decision:** do not add another mandatory bag-OFF debounce in Family Presence by default. That would stack on top of the configured 180s timeout and could unnecessarily delay AWAY/household-all-away. Only introduce an optional additional stability guard if live logs show that the source's 180s timeout still produces spurious OFF events.

**Important blind window:** while the bag has physically left but the provider still reports ON for approximately 180 seconds, Family Presence **cannot apply the strict bag-absence veto yet**. Watch/phone/door/gate logic must stay robust on its own, and shared condominium gate activity must not be considered person identity. This window should be measured in shadow logs.

## Architecture choice: three independent integrations

```text
Bluetooth stack / ESPHome Bluetooth proxies
     ├── Beacon BLE Presence → bag binary_sensor ON/OFF
     └── Watch BLE Presence  → Watch binary_sensor ON/OFF + last_seen_before_off
                                    |
                 Home Assistant standard entities
                                    ↓
                        Family Presence FSM
                    physical events + phone data
                                    ↓
                      inferred person/household state
                                    ↓
                    separate YAML household actions
```

Do **not** merge the two providers and the FSM into a monolith. Their identity resolution (iBeacon vs IRK), BLE cache behavior, lifecycle and independent testing/publication are distinct. Family Presence should consume HA entity contracts and be compatible with alternative BLE providers. A single UI/configuration experience can be considered later without coupling the detection implementation.

## Follow-up checks before production

1. Observe 180s provider OFF transitions, especially when batteries, proxies or scanning become temporarily unavailable; confirm actual bag false OFF rates.
2. Confirm the Family Presence adapter distinguishes real `on→off` and `off→on` from provider startup `unavailable→off/on`.
3. Verify the Watch's ISO timestamp exists on real OFF events; confirm which physical events fall before `last_seen_before_off`.
4. Diagnose the initial ~180s bag-ON blind window with Watch charging at home and shared gate events.
5. Define manual bag priority override only after testing conflicts with the YAML alarm conditions.
6. Optionally correct Beacon BLE Presence README's 5s vs 15s mismatch in its **own repository**, without altering its behavior or reconfiguring sensors.
