# state/wan

<!-- path: state/wan -->
<!-- type: state -->
<!-- response: object -->

[state](../) / wan

---

WAN state: per-device auto_apn and other runtime state.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `devices` | array | Per-device state |

**devices[]**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Device ID (e.g. mdm-41949674) |
| `auto_apn` | object | Auto APN state |

**auto_apn**

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | Finished, etc. |
| `index` | number | Index |
| `plmn` | string | PLMN |
| `mode` | string | Normal, etc. |
| `iccid` | string | SIM ICCID |

### SDK Example
```python
import cp
wan = cp.get('state/wan')
for dev in wan.get('devices', []) or []:
    apn = dev.get('auto_apn', {})
    cp.log(f"{dev.get('id')}: auto_apn state={apn.get('state')} plmn={apn.get('plmn')}")
```

### REST
```
GET /api/state/wan
GET /api/state/wan/devices
```

### Related
- [status/wan](../status/wan/README.md) - WAN status (preferred)
