# control/system

<!-- path: control/system -->
<!-- type: control -->
<!-- response: object -->

[control](../) / system

---

System control: reboot, factory reset, clock, tcpdump, apps, SDK.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `reboot` | null\|number | PUT 1 to reboot |
| `factory_reset` | null | PUT to factory reset |
| `clock` | object | See sub-table |
| `localtime` | string | Current local time (read-only) |
| `tcpdump` | object | Packet capture control |
| `httpserver` | object | HTTP server control |
| `apps` | object | See sub-table |
| `mtls` | object | mTLS (get_csr) |
| `sdk` | object | SDK action |

**clock**

| Field | Type | Description |
|-------|------|-------------|
| `set_time` | number | Unix timestamp to set |
| `set_zone` | string | Timezone (e.g. +7) |
| `set_dst` | boolean | DST enabled |

**apps**

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | App action |

### SDK Example
```python
import cp
# Reboot router
cp.put('control/system/reboot', 1)
# Factory reset (destructive!)
# cp.put('control/system/factory_reset', None)
```

### REST
```
PUT /api/control/system/reboot
Body: 1
```

### Related
- [control/button](#button) - Button simulation
- [control/led](#led) - LED reset

---

## button

`control/button/` - Simulate button presses.

| Field | Type | Description |
|-------|------|-------------|
| `sim_door_open` | boolean | Simulate SIM door open |
| `factory_reset` | boolean | Simulate factory reset button |

---

## led

`control/led/` - LED control.

| Field | Type | Description |
|-------|------|-------------|
| `reset_leds` | null | PUT to reset LEDs |

---

## signal_strength_leds

`control/signal_strength_leds` - Signal strength LED on/off.

| Value | Description |
|-------|-------------|
| `enabled` | LEDs on |
| `disabled` | LEDs off |

```python
cp.put('control/signal_strength_leds', 'enabled')
```
