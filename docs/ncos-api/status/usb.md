# status/usb

<!-- path: status/usb -->
<!-- type: status -->
<!-- response: object -->

[status](../) / usb

---

USB connection status. Keys: connection, usb-serial, int1 (modem), etc.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| *(key)* | string | USB port/function (connection, usb-serial, int1) |
| *(value)* | object | See sub-table |

**usb.{key}**

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | plugged, unplugged |
| `type` | string | modem, etc. (optional) |

### SDK Example
```python
import cp
usb = cp.get('status/usb')
if usb:
    for name, info in usb.items():
        cp.log(f'USB {name}: {info.get("state")}')
```

### REST
```
GET /api/status/usb
```
