# status/opendns

<!-- path: status/opendns -->
<!-- type: status -->
<!-- response: object -->

[status](../) / opendns

---

OpenDNS/Umbrella status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Status (e.g. `notcfg` when not configured) |

### SDK Example
```python
import cp
odns = cp.get('status/opendns')
if odns:
    cp.log(f'OpenDNS: {odns.get("status")}')
```

### REST
```
GET /api/status/opendns
```
