# status/ethernet

<!-- path: status/ethernet -->
<!-- type: status -->
<!-- response: array -->

[status](../) / ethernet

---

Ethernet port status. Array of port objects.

### Fields

Per-port object:

| Field | Type | Description |
|-------|------|-------------|
| `port` | number | Port index |
| `port_name` | string | Display name |
| `enabled` | boolean | Port enabled |
| `config` | string | auto, etc. |
| `link` | string | up, down |
| `link_speed` | string | e.g. 100FD, Unknown |
| `vlan` | object | See sub-table |
| `incoming` | object | See sub-table |
| `outgoing` | object | See sub-table |

**vlan**

| Field | Type | Description |
|-------|------|-------------|
| `tagged` | array | Tagged VLAN IDs |
| `untagged` | array | Untagged VLAN IDs |

**incoming / outgoing**

| Field | Type | Description |
|-------|------|-------------|
| `bytes` | number | Bytes |
| `packets` | number | Packets |
| `errors` | number | Errors |
| `port_mtu` | number | MTU (optional) |
| `poe_power` | string | off, on (optional) |
| `poe_class` | string | CLASS_* (optional) |
| `poe_detect` | string | DETECT_* (optional) |
| `poe_voltage` | number | Volts (optional) |
| `poe_current` | number | Amps (optional) |
| `poe_power_allocation` | number | (optional) |

### SDK Example
```python
import cp
eth = cp.get('status/ethernet')
if eth:
    cp.log(f'Ethernet ports: {len(eth)}')
```

### REST
```
GET /api/status/ethernet
```
