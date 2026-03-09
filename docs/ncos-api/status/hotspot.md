# status/hotspot

<!-- path: status/hotspot -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / hotspot

---

Captive portal / hotspot status: active sessions, clients, and allowed hosts/domains.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `sessions` | object | Session ID → session info |
| `clients` | object | See [hotspot/clients.md](hotspot/clients.md) |
| `allowed` | object | See sub-table |
| `rateLimitTrigger` | boolean | Rate limit triggered |

**allowed**

| Field | Type | Description |
|-------|------|-------------|
| `hosts` | object | Host identifier → host info |
| `domains` | array | Allowed domains |

### SDK Example
```python
import cp
hotspot = cp.get('status/hotspot')
if hotspot:
    clients = hotspot.get('clients', {})
    for ip, c in clients.items():
        cp.log(f'{ip}: {c.get("username")}')
```

### REST
```
GET /api/status/hotspot
```

### Breakout docs (in hotspot/)
- [hotspot/clients.md](hotspot/clients.md) – clients.{ip} object (20+ fields)
