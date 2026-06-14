# GPIO Sample

A simple Ericsson Cradlepoint SDK application that demonstrates GPIO (General Purpose Input/Output) functionality.

## What it does

- Logs all available GPIO pins on the router
- Reads and logs the current value (0 or 1) of each GPIO pin

## Output

The application will log:
- List of available GPIO pins (e.g., power_input, power_output, expander_1, etc.)
- Current digital value (0 or 1) for each GPIO pin

Example:  
```
10:25:21 AM INFO gpio_sample Starting...
10:25:21 AM INFO gpio_sample gpios: ['power_input', 'power_output', 'expander_1', 'expander_2', 'expander_3', 'accessory_1']
10:25:21 AM INFO gpio_sample gpio: power_input
10:25:21 AM INFO gpio_sample gpio value: 0
10:25:21 AM INFO gpio_sample gpio: power_output
10:25:21 AM INFO gpio_sample gpio value: 0
10:25:21 AM INFO gpio_sample gpio: expander_1
10:25:21 AM INFO gpio_sample gpio value: 1
10:25:21 AM INFO gpio_sample gpio: expander_2
10:25:21 AM INFO gpio_sample gpio value: 1
10:25:21 AM INFO gpio_sample gpio: expander_3
10:25:21 AM INFO gpio_sample gpio value: 1
10:25:21 AM INFO gpio_sample gpio: accessory_1
10:25:21 AM INFO gpio_sample gpio value: 0
```

## GPIO Methods

- `cp.get_gpio()` - Get a GPIO value by common pin name
- `cp.get_all_gpios()` - Get GPIO value of all common pin names
- `cp.get_available_gpios()` - Get available common pin names per router model
- `cp.get_raw_gpios()` - Get raw JSON output from `status/gpio`
  
## Supported GPIOs

Common GPIO pins include:
- `power_input` - Power input detection
- `power_output` - Power output control
- `expander_1/2/3` - Expansion connector GPIOs
- `accessory_1` - Accessory connector GPIO
- `sata_1/2/3/4` - SATA expansion connector GPIOs
- `sata_ignition_sense` - SATA expansion connector GPIO

*Note: Available GPIOs depend on the specific router model.*
