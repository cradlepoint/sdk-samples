# status/sdwan_adv

<!-- path: status/sdwan_adv -->
<!-- type: status -->
<!-- response: object -->

[status](../) / sdwan_adv

---

Advanced SD-WAN status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_mode_driver` | object | See sub-table |
| `wan_bonding` | object | See sub-table |
| `forward_error_correction` | object | See sub-table |
| `qoe` | object | See sub-table |
| `link_mon` | object | See sub-table |

**user_mode_driver**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Status (disabled when not used) |

**wan_bonding**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | WAN bonding state |

**forward_error_correction**

| Field | Type | Description |
|-------|------|-------------|
| `stats` | * | FEC stats |

**qoe**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Quality of Experience |

**link_mon**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Link monitoring |

### SDK Example
```python
import cp
sadv = cp.get('status/sdwan_adv')
if sadv:
    umd = sadv.get('user_mode_driver', {})
    cp.log(f'SD-WAN adv: {umd.get("status")}')
```

### REST
```
GET /api/status/sdwan_adv
```
