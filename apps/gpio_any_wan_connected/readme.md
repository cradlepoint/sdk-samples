# gpio_any_wan_connected
Sets a GPIO output pin high when any WAN connection is active, and low when all WAN connections are down. Provides a hardware signal that indicates network connectivity status.

## How It Works

The app polls `status/wan/connection_state` every 1 second. When the state is `connected`, it sets `ACCESSORY_GPIO_1` to high (1). When disconnected, it sets the pin to low (0).

To avoid unnecessary writes, the app only updates the GPIO output when the connection state changes.

## GPIO Pin

| Pin | Direction | Behavior |
|-----|-----------|----------|
| `ACCESSORY_GPIO_1` | Output | High (1) = WAN connected, Low (0) = WAN disconnected |

## Polling Behavior

- Poll interval: 1 second
- Only writes to GPIO when state changes (avoids repeated writes)
- Monitors all WAN connections (not just cellular modems)

## Use Cases

- Drive an external LED indicator showing WAN connectivity
- Trigger an external relay or alert system on WAN failure
- Interface with building management systems via GPIO

## Sample Log Output

```
Starting...
Set control/gpio/ACCESSORY_GPIO_1 to 1
Set control/gpio/ACCESSORY_GPIO_1 to 0
Set control/gpio/ACCESSORY_GPIO_1 to 1
```

## Supported Devices

This app requires a Cradlepoint router with GPIO accessory connector support. Devices with GPIO capabilities include models with the accessory port (e.g., IBR1700, R1900). Check your device's hardware specifications to confirm GPIO availability.

## Requirements

- Router firmware 7.26 or later
- Router model with GPIO accessory connector
- External circuit connected to ACCESSORY_GPIO_1 output pin
