# status/wan/devices/{device_id}/connectors

<!-- path: status/wan/devices/{device_id}/connectors -->
<!-- type: status -->
<!-- response: array -->

[status](../) / [wan](.) / [devices](.) / connectors

---

Pipeline stages (DHCP, AutoAPN, etc.) for bringing up the connection. Each connector has enabled, state, and optionally ipinfo.

### Per-connector Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Connector name (DHCP, AutoCarrier, etc.) |
| `enabled` | boolean | Enabled |
| `state` | string | `connected`, `disconnected` |
| `traits` | array | See sub-table |
| `ipinfo` | object | See sub-table |
| `ip6info` | object | See sub-table |
| `exception` | string | Error if any |

**ipinfo**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | IPv4 info (gateway, ip_address, etc.) when applicable |

**ip6info**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | IPv6 info when applicable |

**traits[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Connector trait |

### SDK Example
```python
import cp
connectors = cp.get(f'status/wan/devices/{device_id}/connectors')
if connectors:
    for c in connectors:
        cp.log(f"{c.get('name')}: {c.get('state')}")
```

### REST
```
GET /api/status/wan/devices/{device_id}/connectors
```

### Example (partial)
```json
{
  "success": true,
  "data": [
    {"name": "DHCP", "enabled": true, "state": "connected", "ipinfo": {...}},
    {"name": "AutoCarrier", "enabled": true, "state": "connected", "ipinfo": null}
  ]
}
```
