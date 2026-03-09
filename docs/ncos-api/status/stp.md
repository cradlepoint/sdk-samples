# status/stp

<!-- path: status/stp -->
<!-- type: status -->
<!-- response: object -->

[status](../) / stp

---

Spanning Tree Protocol. Top-level keys are bridge names (e.g. primarylan3, guestlan4).

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `{bridge_name}` | object | Per-bridge STP info, see sub-table |

**Per-bridge object**

| Field | Type | Description |
|-------|------|-------------|
| `bridge_name` | string | Bridge name |
| `enabled` | boolean | STP enabled |
| `protocol_version` | string | STP version |
| `bridge_priority` | number | Bridge priority |
| `root_bridge` | string | Root bridge |
| `bridge_id` | string | Bridge ID |
| `root_port` | string | Root port |
| `port_info` | object | See sub-table |

**port_info**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Port information |

### SDK Example
```python
import cp
stp = cp.get('status/stp')
if stp:
    for br, info in stp.items():
        cp.log(f'STP {br}: enabled={info.get("enabled")}')
```

### REST
```
GET /api/status/stp
```
