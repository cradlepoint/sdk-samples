# status/wan/sdwan

<!-- path: status/wan/sdwan -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / sdwan

---

SD-WAN status: connected hub and links. Used when SD-WAN hub/spoke is configured.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `connected_hub` | string | Connected hub ID or "None" |
| `links` | object | See sub-table |

**links**

| Field | Type | Description |
|-------|------|-------------|
| *(key)* | string | Link ID |
| *(value)* | object | See sub-table |

**links.{id}**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Link info |

### SDK Example
```python
import cp
sdwan = cp.get('status/wan/sdwan')
if sdwan:
    hub = sdwan.get('connected_hub', 'None')
    links = sdwan.get('links', {})
    cp.log(f'SD-WAN hub: {hub}, links: {len(links)}')
```

### REST
```
GET /api/status/wan/sdwan
```

### Example Response
```json
{
  "success": true,
  "data": {
    "connected_hub": "None",
    "links": {}
  }
}
```
