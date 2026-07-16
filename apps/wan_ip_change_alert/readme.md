# wan_ip_change_alert
Tracks the WAN IP address and sends an NCM alert when it changes. Includes a configurable confirmation delay to prevent false alerts from temporary IP changes (e.g., DHCP renewals that momentarily assign a different IP).

## How It Works

1. Reads the current WAN IP from `status/wan/ipinfo/ip_address`
2. When a new IP is detected:
   - Waits for the configured recheck delay (default: 300 seconds)
   - Re-reads the WAN IP after the delay
   - Only sends an alert if the IP still matches the new address
3. Logs and sends an NCM alert with both the old and new IP addresses

This delay-and-confirm approach avoids alerting on brief IP changes that resolve themselves.

## SDK Appdata Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `wan_ip_change_alert_recheck` | No | 300 | Seconds to wait before confirming IP change |

Set this in System > SDK Data. Lower values mean faster alerts but more risk of false positives. Higher values provide more confidence the change is permanent.

## Alert Example

```
WAN IP Address Changed from 100.97.17.33 to 100.97.17.34
```

## Use Cases

- Monitor static IP assignments for unexpected changes
- Track cellular IP address changes on mobile deployments
- Detect WAN failover events (IP changes when switching interfaces)
- Compliance monitoring for IP-dependent services (VPN endpoints, firewall rules)

## Timing

| Event | Duration |
|-------|----------|
| Poll interval | 1 second |
| Confirmation delay | Configurable (default 300s / 5 minutes) |

## Requirements

- Router firmware 7.26 or later
- Active WAN connection
- NCM connectivity for alert delivery
