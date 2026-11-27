# Client Bandwidth Throttle
Web-based QoS bandwidth limiting for individual LAN clients.

![image](https://github.com/user-attachments/assets/30798d71-913c-4e68-9ab5-c8203f7e3231)

## Features

- Real-time client detection and bandwidth monitoring
- Per-client bandwidth limits (upload/download)
- Configurable default rate limit for new clients, saved to SDK appdata
- Clients that join after the app starts are limited automatically within about 10 seconds
- Live usage statistics with 95th percentile rate calculation
- Per-client limits saved to SDK appdata, so they persist across reboots and redeploys
- Web interface at `http://router_ip:<port>` (the port is shown in the app log, usually 8000; if 8000 is taken, the app uses the next free port and saves it in `client_bandwidth_throttle_web_port`)

## Usage

1. Deploy app to router
2. Access web interface at `http://router_ip:<port>`, using the port from the app log
3. In the Settings panel, set the default rate limit applied to new clients
4. Set bandwidth limits for each individual client as needed
5. Limits are applied immediately via QoS rules

## Settings

The Settings panel sets the default rate limit (Mbps) applied to clients that
do not have a specific limit configured. The value is stored in SDK appdata so
it persists across reboots and redeploys.

Every client gets a limit when the app starts, and the app checks for new
clients every 10 seconds, so a device that joins later gets its saved limit
(or the default) without anyone pressing Set. Changing the default applies
immediately to every client that is on the default. A client you set to a
specific limit with Set keeps that limit until you change it. Setting a client
back to the current default returns it to following the default.

Per-client limits are stored in SDK appdata (`client_limits`), so they survive
reboots, restarts, and redeploys.

## Default Settings

- Default limit: 10 Mbps per client (overridable via the Settings panel)
- Auto-refresh: 5 seconds
- New client check: 10 seconds
- Rate calculation: 95th percentile over 3 samples (15 seconds)

## Appdata Fields

| Field | Required | Description |
| --- | --- | --- |
| `default_limit_mbps` | No | Default rate limit in Mbps for new clients. Valid range 1-1000. Defaults to 10 in code when unset. |
| `client_limits` | No | Per-client limit overrides, written by the app when you press Set. JSON object of MAC address to Mbps, for example `{"aa:bb:cc:dd:ee:ff": 25}`. Clients not listed use the default. You can pre-set or edit it in NCM SDK Data; delete it to clear all overrides. |
| `client_bandwidth_throttle_web_port` | No | Web UI port (1024-65535). If set, the app uses exactly this port. If not set, it uses port 8000, or the next free port up to 8100 if 8000 is busy, and saves it here only in that case. Set or delete it in NCM SDK Data and restart the app; deleting it picks a port automatically again. If the port is invalid or stays busy, the app stops and logs why. |

## Technical Details

- Uses NCOS QoS queues and rules for enforcement
- Tracks clients via status/lan/clients API
- Bandwidth data from status/client_usage API
- Per-client limits stored in the `client_limits` appdata field
