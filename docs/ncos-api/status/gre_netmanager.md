# status/gre_netmanager

<!-- path: status/gre_netmanager -->
<!-- type: status -->
<!-- response: object -->

[status](../) / gre_netmanager

---

GRE tunnel netmanager.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `stats` | object | See sub-table |
| `devices` | object | Tunnel name → device object, see sub-table |

**devices.{name}**

| Field | Type | Description |
|-------|------|-------------|
| `info` | object | See [info](wan/devices/info.md) |
| `stats` | object | See [stats](wan/devices/stats.md) |
| `status` | object | See [status](wan/devices/status.md) |

**stats**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Netmanager stats |

### SDK Example
```python
import cp
gm = cp.get('status/gre_netmanager')
if gm:
    devs = gm.get('devices', {})
    for name, d in devs.items():
        cp.log(f'GRE {name}: {d.get("status", {})}')
```

### REST
```
GET /api/status/gre_netmanager
```
