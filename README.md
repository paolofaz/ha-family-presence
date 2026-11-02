# Family Presence (Home Assistant)

> **Important:** The default `main` branch is currently an **inert HACS-discovery placeholder**. It does not listen to presence sensors, create entities or change alarm behavior.

## Install the experimental shadow version

Family Presence is being developed in [draft PR #1](https://github.com/paolofaz/ha-family-presence/pull/1). For the initial read-only Home Assistant trial, choose the **`v0.1.0a1` prerelease** when downloading this repository through HACS. Enable prerelease/beta versions for the repository if needed. Do **not** install the default `main` branch expecting the integration wizard: the main placeholder intentionally has no config flow.

If your HACS installation does not offer the prerelease, you may manually copy the contents of the tagged `v0.1.0a1` version's `custom_components/family_presence/` folder into `/config/custom_components/family_presence/`; restart Home Assistant before adding Family Presence from Devices & Services. Do not copy the `main` placeholder.

**Keep your existing YAML presence, alarm and heating automations active.** The tagged alpha computes only shadow states; never connect its diagnostic sensors to the alarm. Refer to the [shadow field test plan](https://github.com/paolofaz/ha-family-presence/blob/chore/hacs-ready-foundation/docs/shadow-test-plan.md).

The default branch is deliberately minimal until the integration has passed real-world Home Assistant tests. Passing HACS validation or having a prerelease is not equivalent to production readiness.

License: MIT.
