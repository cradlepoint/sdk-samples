# status/mdns

<!-- path: status/mdns -->
<!-- type: status -->
<!-- response: object -->

[status](../) / mdns

---

mDNS (multicast DNS) status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `mdns` | object | See sub-table |

**mdns**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | mDNS enabled |
| `running` | boolean | mDNS running |
| `interfaces` | array | Interfaces |
| `lan_uuids` | array | LAN UUIDs |

### SDK Example
```python
import cp
mdns = cp.get('status/mdns')
if mdns:
    m = mdns.get('mdns', {})
    cp.log(f'mDNS: enabled={m.get("enabled")} running={m.get("running")}')
```

### REST
```
GET /api/status/mdns
```
