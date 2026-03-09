# status/wan/cm

<!-- path: status/wan/cm -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / cm

---

Connection manager state. Often empty `{}` when not using advanced connection management features.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | object | Keys and structure when CM features are used |

### SDK Example
```python
import cp
cm = cp.get('status/wan/cm')
# Typically empty or minimal
```

### REST
```
GET /api/status/wan/cm
```

### Example Response
```json
{"success": true, "data": {}}
```
