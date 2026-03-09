# status/dns

<!-- path: status/dns -->
<!-- type: status -->
<!-- response: object -->

[status](../) / dns

---

DNS cache/resolver status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `cache` | object | Cache stats, see sub-table |

**cache**

| Field | Type | Description |
|-------|------|-------------|
| `time` | number | Uptime/age |
| `size` | number | Cache size |
| `freed` | number | Freed entries |
| `inserted` | number | Inserted entries |
| `forwarded` | number | Forwarded queries |
| `local` | number | Local queries |
| `servers` | array | Per-server objects, see sub-table |
| `entries` | array | Cache entry objects, see sub-table |

**cache.servers[]**

| Field | Type | Description |
|-------|------|-------------|
| `addr` | string | Server address |
| `port` | number | Server port |
| `queries` | number | Query count |
| `failed` | number | Failed count |

**cache.entries[]**

| Field | Type | Description |
|-------|------|-------------|
| `host` | string | Hostname |
| `addr` | string | Resolved address |
| `type` | string | Record type |
| `flags` | string | Flags |
| `expires` | number | Expiry time |

### SDK Example
```python
import cp
dns = cp.get('status/dns')
if dns:
    cache = dns.get('cache', {})
    cp.log(f'DNS cache: size={cache.get("size")}')
```

### REST
```
GET /api/status/dns
```
