# throttle_cellular_datacap
Enforces bandwidth throttling on all cellular modem interfaces when any modem reaches 100% of its monthly data capacity limit. Automatically removes throttling when the billing cycle resets.

## How It Works

1. On startup, identifies all modem interfaces and their WAN profiles
2. Clears any existing bandwidth throttling (handles router reboot during a throttled state)
3. Polls `status/wan/datacap/completed_alerts/` every 10 seconds
4. When any modem's monthly data cap alert fires:
   - Sets bandwidth ingress/egress limits on ALL modem profiles
   - Enables manual QoS globally
   - Sends an NCM alert
5. When the monthly billing cycle resets and alerts clear:
   - Removes bandwidth limits from all modem profiles
   - Disables manual QoS
   - Sends an NCM alert

## Configuration

### Router Prerequisites

1. **Enable Global Data Usage** in Connection Manager
2. **Enable "Alert on Cap"** on desired cellular modem profile(s)

If "Alert on Cap" is not configured, the app will not detect data overages.

### Throttle Rates

Edit the variables at the top of `throttle_cellular_datacap.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `minbwup` | 512 Kbps | Upload bandwidth limit when throttled |
| `minbwdown` | 512 Kbps | Download bandwidth limit when throttled |
| `maxbwup` | 25000 Kbps | Default max upload (not actively used) |
| `maxbwdown` | 25000 Kbps | Default max download (not actively used) |

## Behavior Details

- Throttling applies to ALL modem profiles, not just the one that exceeded its cap
- Only monitors 100% monthly usage alerts — ignores partial alerts or non-monthly alerts
- Ignores data usage alerts on non-modem interfaces (Ethernet, WWAN)
- Sends NCM alerts on both throttle activation and deactivation
- Includes router name, product, and NCM router ID in alert messages

## NCM Alert Examples

```
Exceeded monthly data usage threshold - reducing LTE data rate for MyRouter - IBR1700 - Router ID: 12345
```

```
Monthly data usage reset - disabling reduced LTE data rate for MyRouter - IBR1700 - Router ID: 12345
```

## Requirements

- Router firmware 7.26 or later
- Data Usage enabled globally in Connection Manager
- "Alert on Cap" configured on at least one modem profile
- NCM connectivity for alert delivery
