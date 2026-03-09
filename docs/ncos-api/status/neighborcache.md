# status/neighborcache

<!-- path: status/neighborcache -->
<!-- type: status -->
<!-- response: array -->

[status](../) / neighborcache

---

ARP/neighbor cache entries.

### Fields (array of objects)

| Field | Type | Description |
|-------|------|-------------|
| `ip` | string | IP address |
| `mac` | string | MAC address |
| `dev` | string | Interface/device |
| *(varies)* | * | Other entry fields |

### SDK Example
```python
import cp
nc = cp.get('status/neighborcache')
if nc:
    cp.log(f'Neighbor cache: {len(nc)} entries')
```

### REST
```
GET /api/status/neighborcache
```
