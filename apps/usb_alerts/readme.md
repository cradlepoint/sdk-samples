# usb_alerts
Sends NetCloud Manager alerts when USB devices are connected or disconnected from the router. Monitors the system log in real-time for USB hotplug events.

## How It Works

The app tails `/var/log/messages` and watches for USB-related kernel messages:
- Lines containing "speed USB" indicate a new USB device connection
- Lines containing "USB disconnect" indicate a device was removed

When detected, the app sends an NCM alert via `cp.alert()` with details about the USB event.

## Alert Examples

**USB Connected:**
```
USB Connected: 2.0 device number 3 using xhci-hcd
```

**USB Disconnected:**
```
USB Disconnected device number 3
```

## Use Cases

- Monitor USB storage devices on remote/unattended routers
- Detect unauthorized USB device connections (security monitoring)
- Track USB modem adapter insertions/removals
- Audit trail for USB device activity

## Viewing Alerts

Alerts appear in:
- NCM Alerts dashboard
- NCM email notifications (if configured)
- NCM API alerts endpoint

## How Detection Works

The app parses kernel log messages from `/var/log/messages`:
- Connection: kernel logs "new high-speed USB device" or similar with "speed USB"
- Disconnection: kernel logs "USB disconnect" with device details

## Requirements

- Router firmware 7.26 or later
- USB port on the router (most models have at least one)
- NCM connectivity for alert delivery

## Notes

- The app runs continuously, tailing the log file
- Only physical USB events are detected (not virtual/internal USB devices)
- The app auto-starts and auto-restarts on failure
