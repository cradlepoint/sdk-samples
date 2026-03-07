# status/gpio

<!-- path: status/gpio -->
<!-- type: status -->
<!-- response: object -->

[status](../) / gpio

---

GPIO pin states: modem detect, LED, power, etc. Flat key-value (pin name → 0/1).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `{pin_name}` | integer | Pin state 0 or 1 (model-specific keys) |

### Model-specific GPIO pins (from cp.py)

Raw keys vary by model. The SDK `cp.get_gpio()` maps logical names to model-specific paths.

**IBR200**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CGPIO_CONNECTOR_INPUT` |
| `power_output` | `CGPIO_CONNECTOR_OUTPUT` |

**IBR600**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CONNECTOR_INPUT` |
| `power_output` | `CONNECTOR_OUTPUT` |

**IBR900**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CONNECTOR_INPUT` |
| `power_output` | `CONNECTOR_OUTPUT` |
| `sata_1` | `SATA_GPIO_1` |
| `sata_2` | `SATA_GPIO_2` |
| `sata_3` | `SATA_GPIO_3` |
| `sata_4` | `SATA_GPIO_4` |
| `sata_ignition_sense` | `SATA_IGNITION_SENSE` |

**IBR1100**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CGPIO_CONNECTOR_INPUT` |
| `power_output` | `CGPIO_CONNECTOR_OUTPUT` |
| `expander_1` | `CGPIO_SERIAL_INPUT_1` |
| `expander_2` | `CGPIO_SERIAL_INPUT_2` |
| `expander_3` | `CGPIO_SERIAL_INPUT_3` |

**R920**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CONNECTOR_GPIO_1` |
| `power_output` | `CONNECTOR_GPIO_2` |

**R980**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CONNECTOR_GPIO_1` |
| `power_output` | `CONNECTOR_GPIO_2` |

All pin names (25 total), alphabetized:

| Pin name | Pin name | Pin name |
|----------|----------|----------|
| `CELLHEALTH_GRN` | `CELLHEALTH_RED` | `CONNECTOR_GPIO_1` |
| `CONNECTOR_GPIO_1_BUFDIR` | `CONNECTOR_GPIO_1_CTL` | `CONNECTOR_GPIO_1_PH_EN` |
| `CONNECTOR_GPIO_2` | `GPIO_RESET_BUTTON` | `HW_WDT` |
| `HW_WDT_OE` | `MODEM_GRN` | `MODEM_RED` |
| `MPCIE_DISABLE` | `MPCIE_RESET` | `NAPA_RESET` |
| `NCM_STATE` | `POWER_EN_USB_EXTERNAL` | `POWER_OFF_CLK` |
| `POWER_OFF_D` | `RESET_MRB` | `SIM1_DETECT` |
| `SIM2_DETECT` | `USB_EXTERNAL_5V_DETECT` | `USB_EXTERNAL_OVC` |
| `USER_GPIO_EN` | | |

**R1900**

| Logical name | Status key |
|--------------|------------|
| `power_input` | `CONNECTOR_GPIO_2` |
| `power_output` | `CONNECTOR_GPIO_1` |
| `expander_1` | `EXPANDER_GPIO_1` |
| `expander_2` | `EXPANDER_GPIO_2` |
| `expander_3` | `EXPANDER_GPIO_3` |
| `accessory_1` | `ACCESSORY_GPIO_1` |

All pin names (50 total), alphabetized:

| Pin name | Pin name | Pin name |
|----------|----------|----------|
| `ACCESSORY_GPIO_1` | `ADC_INT` | `ADC_MODE` |
| `ATTN_RED` | `BT_GPIO` | `BT_RESET` |
| `CONNECTOR_GPIO_1` | `CONNECTOR_GPIO_2` | `EXPANDER_GPIO_1` |
| `EXPANDER_GPIO_1_CTL` | `EXPANDER_GPIO_2` | `EXPANDER_GPIO_2_CTL` |
| `EXPANDER_GPIO_3` | `EXPANDER_GPIO_3_CTL` | `GPIO_RESET_BUTTON` |
| `GPS_ACTIVE_ANT_CLK` | `GPS_BLU` | `GPS_BOOT_MODE_CLK` |
| `GPS_FLIP_FLOP_D` | `GPS_POWER_CLK` | `HW_WDT` |
| `HW_WDT_OE` | `LED_BT` | `LED_SS_0` |
| `LED_SS_1` | `LED_SS_2` | `LED_SS_3` |
| `LED_WIFI` | `MALIBU_RESET` | `MODEM_5G_GRN` |
| `MODEM_GRN` | `MODEM_OK_POWER_OFF` | `MODEM_RED` |
| `MPCIE_DISABLE` | `MPCIE_FCPF` | `MPCIE_RESET` |
| `PCIE_POWER` | `PCIE_SWITCH` | `POWER_EN_USB_EXTERNAL` |
| `POWER_OFF_CLK` | `POWER_OFF_D` | `RESET_MRB` |
| `SIM1_DETECT` | `SIM2_DETECT` | `SIM_SELECT_A` |
| `SIM_SELECT_B` | `SWITCH_RESET` | `USB_EXTERNAL_5V_DETECT` |
| `USB_EXTERNAL_OVC` | `USB_HUB_RESET` | `USB_PASSTHROUGH` |
| `USER_GPIO_EN` | | |

**E3000**

All pin names (56 total), alphabetized. Each key returns 0 or 1.

| Pin name | Pin name | Pin name |
|----------|----------|----------|
| `ANTMAN_PWR_FLT` | `ATTN_RED` | `BT_DETECT` |
| `BT_GPIO` | `BT_POWER_EN` | `BT_RESET` |
| `GPIO_RESET_BUTTON` | `HUB_RESET` | `INTERNAL_MODEM_RESET` |
| `LED_BAR_0` | `LED_BAR_1` | `LED_BAR_10` |
| `LED_BAR_11` | `LED_BAR_12` | `LED_BAR_13` |
| `LED_BAR_14` | `LED_BAR_2` | `LED_BAR_3` |
| `LED_BAR_4` | `LED_BAR_5` | `LED_BAR_6` |
| `LED_BAR_7` | `LED_BAR_8` | `LED_BAR_9` |
| `LED_LOGO` | `LED_MC400_SS_0` | `LED_MC400_SS_1` |
| `LED_MC400_SS_2` | `LED_MC400_SS_3` | `LED_SS_0` |
| `LED_SS_1` | `LED_SS_2` | `LED_SS_3` |
| `LED_WIFI` | `M2_PCIE_RESET` | `MC400_GRN` |
| `MC400_RED` | `MC500_DETECT` | `MODEM_5G_GRN` |
| `MODEM_5G_RED` | `MODEM_GRN` | `MODEM_RED` |
| `NAPA_INT` | `PCIE1_RST_N` | `PCIE_POWER_OFF` |
| `POWER_EN_INT1` | `POWER_EN_MDM1` | `POWER_EN_USB1` |
| `PSU_DET1` | `PSU_DET3` | `PSU_FAST_SHUTDOWN` |
| `PSU_INT` | `PSU_RESET` | `SFP_MODULE_DETECT` |
| `SFP_TX_FLT` | `SIM1_DETECT` | `SIM2_DETECT` |
| `SIM_DOOR_DETECT` | `SIM_SELECT_A` | `SIM_SELECT_B` |
| `SWITCH_SPI_UART` | `USB_5V1_FLT` | `USB_5V2_FLT` |
| `USB_SWITCH_CONTROL` | `VPN_BLU` | `VPN_GRN` |

Other models may expose different keys. Use `cp.get('status/gpio')` for the full raw payload.

### SDK Example
```python
import cp
# Raw status/gpio (model-specific keys)
gpio = cp.get('status/gpio')
if gpio:
    sim1 = gpio.get('SIM1_DETECT')
    cp.log(f'SIM1 detect: {sim1}')

# Model-mapped API (uses cp.get_gpio)
val = cp.get_gpio('power_input')
all_mapped = cp.get_gpio()  # all mapped pins for this model
```

### REST
```
GET /api/status/gpio
```
