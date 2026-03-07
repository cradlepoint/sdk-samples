# status/scepclient

<!-- path: status/scepclient -->
<!-- type: status -->
<!-- response: object -->

[status](../) / scepclient

---

SCEP (certificate enrollment) client status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `result` | object\|null | See sub-table (when available) |

**result**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Enrollment result (status, cert, error, etc.) |

### SDK Example
```python
import cp
scep = cp.get('status/scepclient')
if scep:
    cp.log(f'SCEP: {scep.get("result")}')
```

### REST
```
GET /api/status/scepclient
```
