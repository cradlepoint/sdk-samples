# control/gpio

<!-- path: control/gpio -->
<!-- type: control -->
<!-- response: object -->

[control](../) / gpio

---

GPIO pin control. Top-level keys are pin names; values are 0 or 1. **Read with GET, write with PUT.**

### Fields

Pin names vary by router model. Common patterns:

| Pin Type | Examples | Description |
|----------|----------|-------------|
| Power / detect | `POWER_EN_USB1`, `POWER_EN_MDM1`, `SIM1_DETECT`, `SFP_MODULE_DETECT` | Power enable, presence detect |
| LEDs | `LED_SS_0`, `LED_SS_1`, `LED_MODEM_GRN`, `LED_BAR_0` | LED outputs |
| Modem | `INTERNAL_MODEM_RESET`, `PCIE1_RST_N` | Modem reset |
| USB | `USB_SWITCH_CONTROL`, `USB_5V1_FLT` | USB control |
| IoT | `BT_GPIO`, `BT_POWER_EN`, `BT_RESET` | Bluetooth |

### SDK Example
```python
import cp
# Read all GPIO
gpio = cp.get('control/gpio')
# Set LED on
cp.put('control/gpio/LED_SS_0', 1)
# Set LED off
cp.put('control/gpio/LED_SS_0', 0)
# USB power (model-specific)
cp.put('control/gpio/POWER_EN_USB_EXTERNAL', 1)
```

### REST
```
GET /api/control/gpio
PUT /api/control/gpio/LED_SS_0
Body: 1
```

### Related
- [status/gpio](../status/gpio.md) - GPIO status (pin names)
- [config/system/gpio_actions](../config/dtd/) - GPIO configuration
