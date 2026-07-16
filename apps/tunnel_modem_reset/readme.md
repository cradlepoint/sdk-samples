# tunnel_modem_reset
Monitors VPN tunnels and resets the egress modem if a tunnel stays down. Sends an NCM alert before resetting. Designed for NCX (NetCloud Exchange) tunnel environments where modem issues can cause tunnel failures.

## How It Works

1. On startup, waits up to 10 minutes for all VPN tunnels to come up
2. Polls `status/vpn/tunnels` every 5 seconds
3. If any tunnel is not in the `up` state:
   - Waits 10 seconds for transient recovery
   - Re-checks the specific tunnel
   - If still down, extracts the modem UID from the tunnel name
   - Sends an NCM alert
   - Resets the modem via `control/wan/devices/mdm-{uid}/reset`
   - Waits for all tunnels to recover before resuming monitoring

## Tunnel Name Convention

The app expects tunnel names to contain the modem UID in the format:
```
prefix_MODEMUID_suffix
```

It extracts the modem UID by splitting the tunnel name on `_` and taking the second element.

## Alert Example

```
NCX tunnel tunnel_12345678_primary is down. Resetting modem 12345678
```

## Timing

| Action | Duration |
|--------|----------|
| Initial tunnel wait | Up to 10 minutes |
| Poll interval | 5 seconds |
| Confirmation delay | 10 seconds after detecting down tunnel |
| Post-reset wait | Up to 10 minutes for tunnels to recover |
| Pre-reset delay | 5 seconds (after alert, before reset) |

## Use Cases

- NCX deployments where modem issues cause tunnel drops
- Sites with unreliable cellular connections
- Automated modem recovery without manual intervention

## Requirements

- Router firmware 7.26 or later
- VPN tunnels configured (typically NCX tunnels)
- Tunnel names must include the modem UID as the second underscore-separated field
- NCM connectivity for alert delivery
