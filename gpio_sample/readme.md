# GPIO Sample

A simple Ericsson Cradlepoint SDK application that demonstrates GPIO (General Purpose Input/Output) functionality.

## What it does

- Logs all available GPIO pins on the router
- Reads and logs the current value (0 or 1) of each GPIO pin

## Output

The application will log:
- List of available GPIO pins (e.g., power_input, power_output, expander_1, etc.)
- Current digital value (0 or 1) for each GPIO pin

## Supported GPIOs

Common GPIO pins include:
- `power_input` - Power input detection
- `power_output` - Power output control
- `expander_1/2/3` - Expansion connector GPIOs
- `accessory_1` - Accessory connector GPIO

*Note: Available GPIOs depend on the specific router model.*