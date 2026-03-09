# status/sfp

<!-- path: status/sfp -->
<!-- type: status -->
<!-- response: array -->

[status](../) / sfp

---

SFP module status. Array of SFP port objects.

### Fields (per object)

| Field | Type | Description |
|-------|------|-------------|
| `uid` | string | Port identifier |
| `link` | string | up, down |
| `link_speed` | string | e.g. 1G |

### SDK Example
```python
import cp
sfp = cp.get('status/sfp')
if sfp:
    cp.log(f'SFP modules: {len(sfp)}')
```

### REST
```
GET /api/status/sfp
```
