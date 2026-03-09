# status/wan/devices/{device_id}/config

<!-- path: status/wan/devices/{device_id}/config -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / [devices](.) / config

---

Effective/merged configuration from the matched rule. The "original config" applied when the device was matched. Includes bandwidth, modem settings, failback, etc.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | uuid | Rule ID → `config/wan/rules2/{_id_}` |
| `trigger_string` | string | Match criteria |
| `trigger_name` | string | Rule display name |
| `bandwidth_ingress` | integer | Download kbps |
| `bandwidth_egress` | integer | Upload kbps |
| `def_conn_state` | string | Default connection state |

To change device config, update the rule via `config/wan/rules2/{_id_}`.

### SDK Example
```python
import cp
config = cp.get(f'status/wan/devices/{device_id}/config')
if config:
    rule_id = config.get('_id_')
    # Modify via: cp.put(f'config/wan/rules2/{rule_id}', {...})
```

### REST
```
GET /api/status/wan/devices/{device_id}/config
```

### Related
- [config/wan/rules2/](../../../config-wan-rules2.md)
- [info](info.md) - info.config_id equals config._id_
