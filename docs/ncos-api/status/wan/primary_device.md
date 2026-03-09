# status/wan/primary_device

<!-- path: status/wan/primary_device -->
<!-- type: status -->
<!-- response: string -->

[status](../) / [wan](.) / primary_device

---

Device ID of the currently active WAN connection. Use to look up details under `status/wan/devices/{device_id}`.

### Response Type
`string`

### Format
`{type}-{uid}` (e.g. `mdm-41949674`, `ethernet-wan`)

### SDK Example
```python
import cp
primary = cp.get('status/wan/primary_device')
if primary:
    device_status = cp.get(f'status/wan/devices/{primary}/status')
    cp.log(f'Primary device {primary}: {device_status}')
```

### REST
```
GET /api/status/wan/primary_device
```

### Example Response
```json
{"success": true, "data": "mdm-41949674"}
```

### Related
- [devices/](devices/README.md)
- [connection_state](connection_state.md)
