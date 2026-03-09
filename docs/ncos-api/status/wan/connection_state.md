# status/wan/connection_state

<!-- path: status/wan/connection_state -->
<!-- type: status -->
<!-- response: string -->

[status](../) / [wan](.) / connection_state

---

Current WAN connection state for the router.

### Response Type
`string`

### Common Values
- `connected` - WAN is up
- `disconnected` - No WAN
- `connecting` - In progress

### SDK Example
```python
import cp
state = cp.get('status/wan/connection_state')
if state == 'connected':
    cp.log('WAN is up')
else:
    cp.log(f'WAN state: {state}')
```

### REST
```
GET /api/status/wan/connection_state
```

### Example Response
```json
{"success": true, "data": "connected"}
```

### Related
- [primary_device](primary_device.md)
- [config/wan/](../../config-wan-rules2.md)
