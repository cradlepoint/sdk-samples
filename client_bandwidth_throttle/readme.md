# Client Bandwidth Throttle

Web-based QoS bandwidth limiting for individual LAN clients.

## Features

- Real-time client detection and bandwidth monitoring
- Per-client bandwidth limits (upload/download)
- Live usage statistics with 95th percentile rate calculation
- Persistent limit settings across reboots
- Web interface at http://router_ip:8000

## Usage

1. Deploy app to router
2. Access web interface at http://router_ip:8000
3. Set bandwidth limits for each client
4. Limits are applied immediately via QoS rules

## Default Settings

- Default limit: 10 Mbps per client
- Auto-refresh: 5 seconds
- Rate calculation: 95th percentile over 3 samples (15 seconds)

## Technical Details

- Uses NCOS QoS queues and rules for enforcement
- Tracks clients via status/lan/clients API
- Bandwidth data from status/client_usage API
- Limits stored in tmp/client_limits.json