# status/vti_netmanager

<!-- path: status/vti_netmanager -->
<!-- type: status -->
<!-- response: object -->

[status](../) / vti_netmanager

---

VTI (Virtual Tunnel Interface) netmanager stats.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `stats` | object | See sub-table |

**stats**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | VTI netmanager statistics |

### SDK Example
```python
import cp
vti = cp.get('status/vti_netmanager')
if vti:
    cp.log(f'VTI: {vti.get("stats", {})}')
```

### REST
```
GET /api/status/vti_netmanager
```
