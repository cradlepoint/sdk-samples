# GPIO WLAN Control

Monitors the GPIO connector input and sets `control/wlan/enabled` to match the GPIO value.

The app continuously reads the GPIO connector input and sets WLAN enabled/disabled based on the GPIO value (1 = enabled, 0 = disabled).

## Optional Configuration: System -> SDK Data

- `gpio_wlan_control_toggle`: If set (any value), inverts the GPIO behavior (1 = disabled, 0 = enabled).
