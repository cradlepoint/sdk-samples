# WAN IP Change Alert

Tracks the WAN IP address and sends an alert when it changes. Includes a confirmation delay to prevent false alerts from temporary IP changes.

## Configuration

### System -> SDK Appdata

- **wan_ip_change_alert_recheck**: Number of seconds to wait after detecting an IP change before confirming and sending the alert (default: 300)

## Alert Example

```
WAN IP Address Changed from 100.97.17.33 to 100.97.17.34
```
