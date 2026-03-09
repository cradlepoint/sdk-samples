# status/mount

<!-- path: status/mount -->
<!-- type: status -->
<!-- response: object -->

[status](../) / mount

---

Storage mount and disk usage.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `filesystem` | string | Mount state (e.g. `done`) |
| `disk_usage` | object | See sub-table |

**disk_usage**

| Field | Type | Description |
|-------|------|-------------|
| `total_bytes` | integer | Total storage bytes |
| `free_bytes` | integer | Free bytes |

### SDK Example
```python
import cp
m = cp.get('status/mount')
if m:
    du = m.get('disk_usage', {})
    free_gb = du.get('free_bytes', 0) / (1024**3)
    cp.log(f'Storage: {free_gb:.1f} GB free')
```

### REST
```
GET /api/status/mount
```
