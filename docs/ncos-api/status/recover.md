# status/recover

<!-- path: status/recover -->
<!-- type: status -->
<!-- response: object -->

[status](../) / recover

---

Recovery log.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `log` | object | Recovery log, see sub-table |

**log**

| Field | Type | Description |
|-------|------|-------------|
| `kernel` | array | See sub-table |
| `service_manager` | array | See sub-table |

**log.kernel[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Kernel log entry (string or object) |

**log.service_manager[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Service manager log entry (string or object) |

### SDK Example
```python
import cp
rec = cp.get('status/recover')
if rec:
    sm = rec.get('log', {}).get('service_manager', [])
    cp.log(f'Recover log: {len(sm)} service_manager entries')
```

### REST
```
GET /api/status/recover
```
