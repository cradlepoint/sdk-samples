# status/vxlan

<!-- path: status/vxlan -->
<!-- type: status -->
<!-- response: object -->

[status](../) / vxlan

---

VXLAN tunnel status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `vxlan` | object | Tunnel name → tunnel info, see sub-table |

**vxlan.{name}**

| Field | Type | Description |
|-------|------|-------------|
| `vxlan_iface` | string | VXLAN interface |
| `enabled` | boolean | Enabled |
| `remote_ip` | string | Remote IP |
| `state` | string | Tunnel state |

### SDK Example
```python
import cp
vx = cp.get('status/vxlan')
if vx:
    v = vx.get('vxlan', {})
    for name, info in v.items():
        cp.log(f'VXLAN {name}: {info.get("state")}')
```

### REST
```
GET /api/status/vxlan
```
