# status/remote_modem

<!-- path: status/remote_modem -->
<!-- type: status -->
<!-- response: object -->

[status](../) / remote_modem

---

Remote/captive modem status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `roster` | object | See sub-table |
| `upgrades` | object | See sub-table |
| `metrics` | object | See sub-table |
| `channels` | object | See sub-table |

**roster**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Modem roster entries |

**upgrades**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Upgrade state |

**metrics**

| Field | Type | Description |
|-------|------|-------------|
| `captives` | object | Captive modem details (key → info) |
| `channels` | number | Channel count |
| `modems` | number | Modem count |

**channels**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Channel info |

### SDK Example
```python
import cp
rm = cp.get('status/remote_modem')
if rm:
    m = rm.get('metrics', {})
    cp.log(f'Remote modems: {m.get("modems", 0)}')
```

### REST
```
GET /api/status/remote_modem
```
