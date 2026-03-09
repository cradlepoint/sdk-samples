# status/vsi

<!-- path: status/vsi -->
<!-- type: status -->
<!-- response: array -->

[status](../) / vsi

---

VSI (Virtual Service Interface) status. Array of VSI info.

### Fields (per array element)

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | VSI info object |

### SDK Example
```python
import cp
vsi = cp.get('status/vsi')
if vsi:
    cp.log(f'VSI: {len(vsi)} entries')
```

### REST
```
GET /api/status/vsi
```
