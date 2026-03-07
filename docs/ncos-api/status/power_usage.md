# status/power_usage

<!-- path: status/power_usage -->
<!-- type: status -->
<!-- response: object -->

[status](../) / power_usage

---

Power consumption (Watts) by subsystem. Requires hardware support.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `system_power` | float | System baseline |
| `cpu_power` | float | CPU |
| `modem_power` | float | Cellular modem |
| `wifi_power` | float | WiFi |
| `sfp_power` | float | SFP module |
| `poe_pse_power` | float | PoE PSE |
| `ethernet_ports_power` | float | Ethernet ports |
| `bluetooth_power` | float | Bluetooth |
| `usb_power` | float | USB |
| `gps_power` | float | GPS |
| `led_power` | float | LEDs |
| `total` | float | Total (Watts) |

### SDK Example
```python
import cp
pw = cp.get('status/power_usage')
if pw:
    cp.log(f'Power: {pw.get("total")}W total, modem={pw.get("modem_power")}W')
```

### REST
```
GET /api/status/power_usage
```
