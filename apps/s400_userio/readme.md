# s400_userio
Demonstrates controlling the user I/O pins on the S400 platform. Reads the power connector GPIO inputs and drives the expansion module LVTTL outputs in a sequential pattern based on input state.

## How It Works

The app continuously:
1. Reads two power connector inputs: `pwr-connector-user-io-1-data` and `pwr-connector-user-io-2-data`
2. Mirrors input 2 directly to expansion module output 9 (`em-user-io-9-data`)
3. Runs a sequential LED-chase pattern on outputs 0-4, with direction determined by input 1:
   - Input 1 low → forward sequence (0, 1, 2, 3, 4)
   - Input 1 high → reverse sequence (4, 3, 2, 1, 0)
4. Each output is set high with a 200ms delay between them, then all are cleared

## GPIO Pin Mapping

### Inputs (Power Connector)

| Pin | Path | Purpose |
|-----|------|---------|
| IO-1 | `status/gpio/pwr-connector-user-io-1-data` | Controls sequence direction |
| IO-2 | `status/gpio/pwr-connector-user-io-2-data` | Mirrors to EM output 9 |

### Outputs (Expansion Module)

| Pin | Path | Purpose |
|-----|------|---------|
| IO-0 to IO-4 | `control/gpio/em-user-io-{0-4}-data` | Sequential pattern outputs |
| IO-9 | `control/gpio/em-user-io-9-data` | Mirror of power connector IO-2 |

## Use Cases

- Driving external indicator LEDs
- Interfacing with industrial control systems
- Testing GPIO functionality on S400 hardware
- Sequential relay activation

## Requirements

- S400 router platform
- Router firmware 7.26 or later
- Expansion module with LVTTL I/O capability
- External circuits connected to the GPIO pins
