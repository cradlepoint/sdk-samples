# Client Bandwidth Throttle
Web-based QoS bandwidth limiting for individual LAN clients.

![image](https://github.com/user-attachments/assets/30798d71-913c-4e68-9ab5-c8203f7e3231)

## Features

- Real-time client detection and bandwidth monitoring
- Per-client bandwidth limits (upload/download)
- Configurable default rate limit for new clients, saved to SDK appdata
- Live usage statistics with 95th percentile rate calculation
- Persistent limit settings across reboots
- Web interface at http://router_ip:8000

## Usage

1. Deploy app to router
2. Access web interface at http://router_ip:8000
3. In the Settings panel, set the default rate limit applied to new clients
4. Set bandwidth limits for each individual client as needed
5. Limits are applied immediately via QoS rules

## Settings

The Settings panel sets the default rate limit (Mbps) applied to clients that
do not have a specific limit configured. The value is stored in SDK appdata so
it persists across reboots and redeploys.

## Default Settings

- Default limit: 10 Mbps per client (overridable via the Settings panel)
- Auto-refresh: 5 seconds
- Rate calculation: 95th percentile over 3 samples (15 seconds)

## Appdata Fields

| Field | Required | Description |
| --- | --- | --- |
| `default_limit_mbps` | No | Default rate limit in Mbps for new clients. Valid range 1-1000. Defaults to 10 in code when unset. |

## Technical Details

- Uses NCOS QoS queues and rules for enforcement
- Tracks clients via status/lan/clients API
- Bandwidth data from status/client_usage API
- Limits stored in tmp/client_limits.json
