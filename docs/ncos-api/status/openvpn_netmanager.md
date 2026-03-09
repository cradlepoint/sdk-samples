# status/openvpn_netmanager

<!-- path: status/openvpn_netmanager -->
<!-- type: status -->
<!-- response: object -->

[status](../) / openvpn_netmanager

---

OpenVPN netmanager.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `stats` | object | See sub-table |
| `devices` | object | Tunnel ID → device object, see sub-table |

**devices.{id}**

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
ov = cp.get('status/openvpn_netmanager')
if ov:
    devs = ov.get('devices', {})
    cp.log(f'OpenVPN devices: {len(devs)}')
```

### REST
```
GET /api/status/openvpn_netmanager
```
