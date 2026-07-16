# power_alert
Sends a NetCloud Manager alert when external power is lost or restored. Designed for battery-powered devices that can detect power source changes.

## How It Works

The app monitors `status/system/battery/ext_power` every 1 second. When the value transitions:
- From powered to unpowered → sends alert: "External power lost!"
- From unpowered to powered → sends alert: "External power restored!"

Alerts are sent via `cp.alert()` which delivers them to NCM for visibility in the alerts dashboard.

## Use Cases

- Remote monitoring of powered equipment (e.g., router in a vehicle loses ignition power)
- Theft detection (device unplugged from power)
- UPS/battery switchover notification
- Fleet management (vehicle ignition on/off tracking)

## Supported Devices

Only works on devices with a battery and external power detection:
- E100
- X10 (E3000)

Other Cradlepoint models without batteries do not have the `status/system/battery/ext_power` status path.

## Alert Delivery

Alerts appear in:
- NCM Alerts dashboard
- NCM email notifications (if configured)
- NCM API alerts endpoint

## Sample Log Output

No log output is generated — the app uses `cp.alert()` which sends directly to NCM.

## Requirements

- Router firmware 7.26 or later
- Battery-powered Cradlepoint device (E100, X10)
- NCM connectivity for alert delivery
