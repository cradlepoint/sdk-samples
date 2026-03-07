# status/feature

<!-- path: status/feature -->
<!-- type: status -->
<!-- response: object -->

[status](../) / feature

---

Feature/license status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `db` | array | Per-feature entries, see sub-table |
| `expiring_alert` | object\|null | See sub-table (optional) |

**db[]** (array of arrays: `[uuid, name, expires_days, remaining_days]`)

| Index | Type | Description |
|-------|------|-------------|
| 0 | string | Feature UUID |
| 1 | string | Feature name |
| 2 | number | Days until expiry |
| 3 | number | Remaining days |

**expiring_alert**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | object | Alert structure when features expiring |

### SDK Example
```python
import cp
feat = cp.get('status/feature')
if feat:
    db = feat.get('db', [])
    cp.log(f'Features: {len(db)}')
```

### REST
```
GET /api/status/feature
```
