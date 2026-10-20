# TRMNL Terminus (BYOS) for Home Assistant

> ## ⚠️ Vibe-coded adaptation
>
> This is Home Assistant's official [TRMNL integration](https://www.home-assistant.io/integrations/trmnl/)
> (by [@joostlek](https://github.com/joostlek)), re-targeted at
> [Terminus](https://github.com/usetrmnl/terminus), TRMNL's self-hosted server.
> Written with Claude Code, reviewed and tested by a human on one TRMNL X.
> Has tests, has rough edges. Read the code before trusting it.

## Why

- The official integration talks to the TRMNL cloud only.
- Devices on Terminus were invisible to Home Assistant.
- Terminus already stores the battery level and more. This reads it.

## Install

**Requirements:** Home Assistant 2026.10+, a reachable Terminus, and its login (email + password).

**HACS:** Integrations → ⋮ → *Custom repositories* → paste
`https://github.com/TobiasGrothmann/homeassistant-terminus-battery`, category *Integration* → install → restart.

**Manual:** copy `custom_components/trmnl_terminus` into your `custom_components` folder → restart.

## Set up

Settings → Devices & services → *Add integration* → **TRMNL Terminus**

| Field | Example |
|---|---|
| Server URL | `http://terminus.local:3000` |
| Email | your Terminus login |
| Password | your Terminus password |

- Polls every 2 minutes.
- Devices added or removed in Terminus show up or vanish without a restart.
- *Reconfigure* on the entry changes URL or credentials.

## What you get

Per device:

| Entity | Type | Enabled |
|---|---|---|
| **Battery** | sensor, % | yes |
| Charging | binary sensor | yes |
| Signal strength | sensor, dBm | yes |
| Last seen | sensor, timestamp | yes |
| Sleep mode | switch | yes |
| Sleep start time / Sleep end time | time | yes |
| Battery voltage | sensor, V | no |
| Wi-Fi band | sensor, GHz | no |
| Firmware version | sensor | no |
| Wake reason | sensor | no |
| Refresh rate | sensor, s | no |
| Wake duration | sensor, ms | no |

- **Battery** is the percentage the device itself reports (TRMNL X gas gauge).
  TRMNL OG has no gauge: enable **Battery voltage** instead.
- **Device card** shows label, model ("TRMNL X"), firmware, MAC, and a link to
  the device page in Terminus.
- **Sleep mode** on = both times set. Off clears them. On again restores the
  last schedule, or 22:00 to 06:00.

Use it for: low-battery notifications, "has not checked in since yesterday"
alerts, a battery card on your dashboard, toggling sleep from an automation.

Screenshots will follow.

## Development

```bash
uv venv .venv --python 3.14
uv pip install --python .venv/bin/python \
  homeassistant==2026.10.2 pytest-homeassistant-custom-component==0.13.373
.venv/bin/python -m pytest
```

- `scripts/deploy.sh` copies the integration to a Home Assistant OS box over
  SSH (*Terminal & SSH* add-on) and restarts Core.
- `scripts/release.sh 0.1.1` bumps the version, pushes, waits for the
  Validate workflow and publishes the GitHub release that HACS picks up.
- Terminus API used: `POST /login`, `GET /api/devices`, `GET /api/models`,
  `PATCH /api/devices/:id`.

## License and credits

GPL-3.0-or-later, see `LICENSE`. Derived from the Apache-2.0 `trmnl`
integration in Home Assistant Core, see `NOTICE`.

Thanks to [@joostlek](https://github.com/joostlek) for the original
integration, to [TRMNL](https://trmnl.com) and Brooke Kuhlmann for Terminus,
and to [Beat2er/homeassistant-trmnl-battery](https://github.com/Beat2er/homeassistant-trmnl-battery)
for the prior art.
