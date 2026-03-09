# status/gre

<!-- path: status/gre -->
<!-- type: status -->
<!-- response: object -->

[status](../) / gre

---

GRE (Generic Routing Encapsulation) tunnel status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `running` | boolean | GRE service running |
| `tunnels` | array | Configured tunnels, see sub-table |
| `global` | object | See sub-table |
| `service` | object | See sub-table (optional) |

**service**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | GRE service state |
| `enabled` | array | Enabled GRE services |
| `sdwan` | boolean | SD-WAN mode |
| `tunnel_action` | object | See sub-table (optional) |

**tunnels[]**

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | uuid | Tunnel config ID |
| `name` | string | Tunnel name |
| `enabled` | boolean | Tunnel enabled |
| `state` | string | up, down |
| `remote_gateway` | array | Remote gateway IP(s) |
| `mtu` | integer | MTU |
| `data_in` | string | Traffic in |
| `data_out` | string | Traffic out |
| `connections` | array | See sub-table |
| `cli` | string | CLI output (optional) |
| `dead_peer_timeout` | integer | DPD timeout (optional) |

**tunnels[].connections[]**

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | string | Connection config ID |
| `local` | string | Local IP |
| `remote` | string | Remote IP |
| `sas` | array | Security associations |

**global**

| Field | Type | Description |
|-------|------|-------------|
| `policy` | string | Policy |
| `state` | string | State |
| `config` | string | Config |

**tunnel_action**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tunnel name |
| `action` | string | start, stop |

### SDK Example
```python
import cp
gre = cp.get('status/gre')
if gre:
    for t in gre.get('tunnels', []):
        cp.log(f"GRE {t.get('name')}: {t.get('state')} gw={t.get('remote_gateway')}")
```

### REST
```
GET /api/status/gre
```

### Example Response (partial)
```json
{
  "success": true,
  "data": {
    "running": true,
    "tunnels": [
      {
        "_id_": "00000000-e18b-3714-86cd-152498cbeeec",
        "name": "asdf",
        "enabled": true,
        "state": "up",
        "remote_gateway": ["6.7.8.9"],
        "mtu": 1476,
        "data_in": "0 / 0",
        "data_out": "0 / 0",
        "connections": [{"local": "0.0.0.0", "remote": "0.0.0.0", "sas": []}]
      }
    ],
    "enabled": ["gre"]
  }
}
```
