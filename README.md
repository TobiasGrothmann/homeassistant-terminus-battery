# TRMNL Terminus (BYOS) for Home Assistant

Home Assistant integration for TRMNL devices served by a self-hosted
[Terminus](https://github.com/usetrmnl/terminus) server (TRMNL's
"bring your own server"). It reads device status from Terminus's API and
exposes it as entities, most importantly the **battery percentage** of a
TRMNL X.

The core `trmnl` integration only talks to the TRMNL cloud. This one talks to
your Terminus instead. It is modelled on the core integration's structure.

## What you get

Per device known to Terminus:

| Entity | Type | Enabled | Source field |
|---|---|---|---|
| Battery | sensor, % | yes | `battery_charge` |
| Charging | binary sensor | yes | `charging` |
| Signal strength | sensor, dBm | yes | `wifi_signal` |
| Last seen | sensor, timestamp | yes | `synced_at` |
| Sleep mode | switch | yes | both sleep times set |
| Sleep start time / Sleep end time | time | yes | `sleep_start_at` / `sleep_stop_at` |
| Battery voltage | sensor, V | no | `battery_voltage` |
| Wi-Fi band | sensor, GHz | no | `wifi_band` |
| Firmware version | sensor | no | `firmware_version` |
| Wake reason | sensor | no | `wake_reason` |
| Refresh rate | sensor, s | no | `refresh_rate` |
| Wake duration | sensor, ms | no | `wake_duration` |

The device card shows the Terminus label, model (for example "TRMNL X"),
firmware version and MAC address, and links to the device page in Terminus.

### Values are reported, never estimated

The integration passes through what Terminus holds. It does not convert
voltage into a percentage. A TRMNL X reports its gas-gauge percentage on
every check-in and Terminus stores it as `battery_charge`. Devices without a
gauge (TRMNL OG) leave that field at `0`, which the integration shows as
*unknown*; enable the battery voltage sensor for those. The same applies to a
`0` voltage, RSSI or Wi-Fi band: Terminus's default means "never reported".

### Sleep schedule

Terminus has no on/off flag for sleep. A schedule is active when both times
are set. The switch therefore clears both times when turned off and, when
turned on, restores the last schedule it saw (or 22:00 to 06:00 if there
never was one). Setting one time while the other is empty fills the other
with the same defaults.

## Requirements

- Home Assistant 2026.10 or newer.
- A reachable Terminus server and a Terminus user (the email and password you
  use for its web interface). The integration logs in with them and obtains
  a JWT; it logs in again automatically when the token expires.

## Installation

### HACS (custom repository)

1. HACS → Integrations → three-dots menu → **Custom repositories**.
2. Add this repository's URL with category **Integration**.
3. Install **TRMNL Terminus (BYOS)** and restart Home Assistant.

### Manual

Copy `custom_components/trmnl_terminus` into the `custom_components` folder
of your Home Assistant configuration directory and restart. On Home Assistant
OS the easiest ways to get files there are the **Samba share** add-on or the
**Terminal & SSH** add-on (see "Deploying over SSH" below).

## Configuration

Settings → Devices & services → **Add integration** → "TRMNL Terminus".

| Field | Example |
|---|---|
| Server URL | `http://terminus.local:3000` |
| Email | your Terminus login |
| Password | your Terminus password |

Devices are polled every 2 minutes. Devices added to or removed from Terminus
appear and disappear without a restart.

Use **Reconfigure** on the integration entry to change the URL or
credentials.

## Deploying over SSH (development)

1. In your Home Assistant user profile enable **Advanced mode**.
2. Settings → Add-ons → Add-on store → install **Terminal & SSH**.
3. In the add-on's Configuration tab paste your public key under
   `authorized_keys` (for example the contents of `~/.ssh/id_ed25519.pub`),
   set the network port to `22`, save and start the add-on.
4. From this repository:

   ```bash
   HA_SSH_HOST=root@homeassistant.local scripts/deploy.sh
   ```

   This copies the integration to `/config/custom_components/trmnl_terminus`
   and restarts Core.

## Development

```bash
uv venv .venv --python 3.14
uv pip install --python .venv/bin/python \
  homeassistant==2026.10.2 pytest-homeassistant-custom-component==0.13.373
.venv/bin/pytest
```

`RESEARCH.md` documents the Terminus API, the TRMNL X battery headers and the
survey of existing solutions that led to this design.

## Terminus API notes

- Login: `POST /login` with JSON `{"login": …, "password": …}` returns
  `access_token`. Tokens are sent as `Authorization: Bearer …`.
- Token lifetime is 30 minutes unless Terminus runs with
  `SESSION_EXPIRATION_ENABLED=false`. The integration re-logs in on 401 and
  never more than once per request.
- `GET /api/devices`, `GET /api/models`, `PATCH /api/devices/:id` with
  `{"device": {…}}`.
- Requests from private subnets are not rate limited; requests without a
  `User-Agent` are blocked.
