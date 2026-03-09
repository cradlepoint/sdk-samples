# status/wan/devices/{device_id}/info

<!-- path: status/wan/devices/{device_id}/info -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / [devices](.) / info

---

Device identity and properties. Used for rule matching in `config/wan/rules2/`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `config_id` | uuid | Matched rule ID → `config/wan/rules2/{config_id}` |
| `type` | string | `mdm`, `ethernet` |
| `uid` | string | Device unique ID |
| `sim` | string | SIM slot (`sim1`, `sim2`) - modems only |
| `port` | string | Port (`int1`, `wan`, `sfp0`) |
| `tech` | string | Cellular tech (`lte/3g`, `lte`) - modems only |
| `model` | string | Model name |
| `manufacturer` | string | Manufacturer |
| `service_type` | string | e.g. LTE |
| `carrier_id` | string | Carrier name - modems only |

### SDK Example
```python
import cp
info = cp.get(f'status/wan/devices/{device_id}/info')
if info:
    config_id = info.get('config_id')
    rule = cp.get(f'config/wan/rules2/{config_id}') if config_id else None
```

### REST
```
GET /api/status/wan/devices/{device_id}/info
```

### Related
- [config/wan/rules2/](../../../config-wan-rules2.md)
