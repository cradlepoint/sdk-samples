# status/wan/devices

<!-- path: status/wan/devices -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / devices

---

Per-device status. Keys are device IDs (`mdm-41949674`, `ethernet-wan`). Created when a detected WAN device matches a rule in `config/wan/rules2/`.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `{device_id}` | object | Per-device object, see sub-table |

**Per-device object**

| Field | Type | Description |
|-------|------|-------------|
| `info` | object | [info.md](info.md) |
| `status` | object | [status.md](status.md) |
| `stats` | object | [stats.md](stats.md) |
| `config` | object | [config.md](config.md) |
| `connectors` | array | [connectors.md](connectors.md) |
| `diagnostics` | object | [diagnostics.md](diagnostics.md) (mdm only) |

### Structure (per device)
```
{device_id}/
├── info        - [info.md](info.md)
├── status      - [status.md](status.md)
├── stats       - [stats.md](stats.md)
├── config      - [config.md](config.md)
├── connectors  - [connectors.md](connectors.md)
└── diagnostics - [diagnostics.md](diagnostics.md) (mdm only)
```

### Device Types
- `mdm-{uid}` - Cellular modem
- `ethernet-wan` - Ethernet WAN port
- `ethernet-sfp0` - SFP WAN port

### SDK Example
```python
import cp
devices = cp.get('status/wan/devices')
if devices and isinstance(devices, dict):
    for dev_id, dev in devices.items():
        status = dev.get('status', {}) if isinstance(dev, dict) else {}
        conn = status.get('connection_state', 'unknown')
        cp.log(f'{dev_id}: {conn}')
```

### REST
```
GET /api/status/wan/devices
GET /api/status/wan/devices/{device_id}
```

### Related
- [config/wan/rules2/](../../../config-wan-rules2.md) - Rule matching, config_id link
