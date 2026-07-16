# gpio_wlan_control
Controls the router's WiFi enabled/disabled state based on a GPIO input pin. Allows external hardware (switch, relay, or signal) to turn WiFi on or off.

## How It Works

The app reads the `power_input` GPIO value every 1 second. When the input is high (non-zero), WiFi is enabled. When low (zero), WiFi is disabled. An optional toggle setting inverts this behavior.

Only updates the WLAN state when the GPIO value actually changes, avoiding unnecessary writes.

## GPIO Input

| Pin | Direction | Behavior |
|-----|-----------|----------|
| `power_input` | Input | High = enable WiFi, Low = disable WiFi (invertible via appdata) |

## SDK Appdata Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `gpio_wlan_control_toggle` | No | Set to any value to invert the GPIO logic (high = disable WiFi, low = enable WiFi) |

When the toggle appdata field is set (to any non-null value), the behavior is inverted:
- GPIO high → WiFi **disabled**
- GPIO low → WiFi **enabled**

## Polling Behavior

- Poll interval: 1 second
- Double-checks GPIO and appdata reads (with 100ms delay) to avoid false positives
- Only updates WLAN state on change

## Use Cases

- Physical switch to disable WiFi in sensitive environments
- Automated WiFi control based on external signal
- Time-based WiFi control via external timer relay

## Sample Log Output

```
Starting...
Set WLAN enabled to True
Set WLAN enabled to False
```

## Supported Devices

Requires a Cradlepoint router with GPIO connector support. The `power_input` GPIO must be available on the device model. Check your router's hardware specifications for GPIO pin availability.

## Requirements

- Router firmware 7.26 or later
- Router model with GPIO connector (power_input pin)
- External signal source connected to power_input GPIO
