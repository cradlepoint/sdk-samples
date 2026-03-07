# status/wired_8021x

<!-- path: status/wired_8021x -->
<!-- type: status -->
<!-- response: object -->

[status](../) / wired_8021x

---

802.1X wired auth status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | 802.1X status |
| `ignored` | array | See sub-table |
| `wired` | array | See sub-table |

**ignored[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Ignored entry |

**wired[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Per-port wired auth info (port, state, etc.) |

### SDK Example
```python
import cp
w8021x = cp.get('status/wired_8021x')
if w8021x:
    cp.log(f'802.1X: {w8021x.get("status")} wired={len(w8021x.get("wired", []))}')
```

### REST
```
GET /api/status/wired_8021x
```
