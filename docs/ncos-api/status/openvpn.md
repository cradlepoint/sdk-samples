# status/openvpn

<!-- path: status/openvpn -->
<!-- type: status -->
<!-- response: object -->

[status](../) / openvpn

---

OpenVPN tunnel status and stats.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `stats` | array | Per-tunnel stats, see sub-table |
| `tunnels` | array | Tunnel interface info, see sub-table |

**stats[]**

| Field | Type | Description |
|-------|------|-------------|
| `tunnel_name` | string | Tunnel name |
| `state` | string | idle/down, up |
| `mode` | string | Site-to-Site, etc. |
| `device_type` | string | Routed, etc. |
| `local_address` | string | Local IP |
| `remote_address` | string | Remote IP |
| `bytes_in` | string | Traffic in (e.g. 0.00B) |
| `bytes_out` | string | Traffic out |
| `updated_connected` | string | Last update timestamp |

**tunnels[]**

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | uuid | Tunnel config ID |
| `info` | object | See sub-table |

**tunnels[].info**

| Field | Type | Description |
|-------|------|-------------|
| `dev` | string | Device (e.g. tun0) |
| `ifconfig_local` | string | Local IP |
| `ifconfig_remote` | string | Remote IP |
| `state` | string | up, down |

### SDK Example
```python
import cp
ovpn = cp.get('status/openvpn')
if ovpn:
    for s in ovpn.get('stats', []):
        cp.log(f"OpenVPN {s.get('tunnel_name')}: {s.get('state')} local={s.get('local_address')}")
```

### REST
```
GET /api/status/openvpn
```

### Example Response (partial)
```json
{
  "success": true,
  "data": {
    "stats": [
      {
        "tunnel_name": "asdf",
        "state": "idle/down",
        "mode": "Site-to-Site",
        "device_type": "Routed",
        "local_address": "5.6.74.5",
        "remote_address": "54.22.5.6",
        "bytes_in": "0.00B",
        "bytes_out": "560.00B"
      }
    ],
    "tunnels": [
      {
        "_id_": "00000000-8e17-3bfa-aa58-d3cdff7748bf",
        "info": {
          "dev": "tun0",
          "ifconfig_local": "5.6.74.5",
          "ifconfig_remote": "5.6.74.6",
          "state": "up"
        }
      }
    ]
  }
}
```
