# status/l2tp

<!-- path: status/l2tp -->
<!-- type: status -->
<!-- response: object -->

[status](../) / l2tp

---

L2TP VPN tunnel status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tunnels` | array | Tunnel entries, see sub-table |
| `ppp` | array | See sub-table |

**tunnels[]**

| Field | Type | Description |
|-------|------|-------------|
| `{tunnel_name}` | string | Status (e.g. enabled) |
| `ppp` | integer | PPP index |

**ppp[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | PPP session detail (interface, state, etc.) |

### SDK Example
```python
import cp
l2tp = cp.get('status/l2tp')
if l2tp:
    for t in l2tp.get('tunnels', []):
        cp.log(f'L2TP tunnel: {t}')
```

### REST
```
GET /api/status/l2tp
```

### Example Response
```json
{
  "success": true,
  "data": {
    "tunnels": [
      {"asdf": "enabled", "ppp": 0}
    ],
    "ppp": []
  }
}
```
