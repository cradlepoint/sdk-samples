# rate_limit
Toggles between two QoS rules based on cellular data cap alerts. When the monthly data cap is reached, disables rule 1 (normal) and enables rule 2 (throttled). When the billing cycle resets, restores the normal rule.

## How It Works

The app polls `status/wan/datacap/completed_alerts/0/alerts` every 10 seconds:
- When a data cap alert appears and throttling is not active → disables QoS rule 0, enables QoS rule 1
- When the alert clears (new billing cycle) and throttling is active → enables QoS rule 0, disables QoS rule 1

## Prerequisites

1. **Data Usage** must be enabled in Connection Manager
2. **Data cap alert** ("Alert on Cap") must be configured on the modem profile
3. **Two QoS rules** must be configured:
   - Rule 0: Normal bandwidth policy (enabled by default)
   - Rule 1: Reduced bandwidth policy (disabled by default)

## QoS Rule Setup Example

| Rule | Purpose | Default State | Bandwidth |
|------|---------|---------------|-----------|
| Rule 0 | Normal operation | Enabled | Full speed |
| Rule 1 | Data cap reached | Disabled | Throttled (e.g., 512 Kbps) |

## Behavior

- Checks every 10 seconds for datacap alerts
- Only toggles rules on state change (not every poll)
- Automatically resets when the monthly billing cycle clears the alert
- Logs state transitions

## Sample Log Output

```
Starting...
Exceeded monthly data usage threshold - implementing reduced bandwidth QoS rule.
Monthly data usage reset - disabling reduced bandwidth QoS rule.
```

## Comparison with throttle_cellular_datacap

This app is simpler — it just toggles pre-configured QoS rules. The `throttle_cellular_datacap` app dynamically sets bandwidth limits on modem profiles and enables/disables QoS globally.

## Requirements

- Router firmware 7.26 or later
- Data Usage enabled in Connection Manager
- Data cap alert configured on at least one modem profile
- Two QoS rules pre-configured (rule 0 = normal, rule 1 = throttled)
