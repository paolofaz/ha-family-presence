# Family Presence v0.1.0a2 — Alpha 2 / Shadow-only

This prerelease corrects the integration category in `manifest.json`:

- Before: `integration_type: helper` — Home Assistant offered Family Presence as an *Aiutante*, rather than as a configurable integration in the normal **Dispositivi e servizi → Aggiungi integrazione** flow.
- Now: `integration_type: hub` — the household aggregates multiple persons and input entities.
- `config_flow: true` and the full configuration wizard remain enabled in this prerelease.
- All experimental code is unchanged: it computes simulated diagnostics and **does not** control alarms, locks or heating.

## How to create the release on GitHub

1. Open https://github.com/paolofaz/ha-family-presence/releases/new
2. Choose **New tag** `v0.1.0a2`.
3. Choose **Target** branch `chore/hacs-ready-foundation` (not `main`).
4. Release title: `Family Presence 0.1.0 Alpha 2 — Shadow testing`.
5. Check **Set as a pre-release** and publish.

**Do not move or modify the existing `v0.1.0a1` tag**: a prerelease tag is an immutable historical testing reference. The version field in the development branch was bumped to `0.1.0a2` for the new tag.

## Installing or updating via HACS

In HACS, open **Family Presence** → Download / Redownload → **Need a different version?** → `v0.1.0a2`. Enable beta/prerelease versions if necessary. Restart Home Assistant to reload the manifest.

If the previous `v0.1.0a1` is currently installed and Home Assistant only offers the integration under **Aiutanti**, replace it with `v0.1.0a2` first, then restart. Only then go to **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Family Presence**.

**Do not install the `main` placeholder:** it contains a discovery-only, deliberately inert integration. It is not the alpha being tested.

## Safety

Keep the original family presence YAML package enabled, including its separate alarm/heating automations. Do not connect shadow diagnostic sensors to live automation conditions. The config flow and entity lifecycle still require validation in the actual Home Assistant instance; HACS/hassfest CI passing does not guarantee installation works.
