# status/qos

<!-- path: status/qos -->
<!-- type: status -->
<!-- response: object -->

[status](../) / qos

---

QoS status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | QoS enabled |
| `queues` | array | See sub-table |

**queues[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Queue entry (name, stats, etc.) when configured |

### SDK Example
```python
import cp
qos = cp.get('status/qos')
if qos:
    cp.log(f'QoS: enabled={qos.get("enabled")} queues={len(qos.get("queues", []))}')
```

### REST
```
GET /api/status/qos
```
