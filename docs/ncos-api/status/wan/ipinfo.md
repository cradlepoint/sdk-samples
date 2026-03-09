# status/wan/ipinfo

<!-- path: status/wan/ipinfo -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / ipinfo

---

IP configuration for the primary WAN connection.

### Response Type
`object`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `primary` | string | Device ID providing this IP info |
| `ip_address` | string | WAN IPv4 address |
| `gateway` | string | Default gateway |
| `netmask` | string | Subnet mask |
| `dns` | array | DNS servers (strings) |

### SDK Example
```python
import cp
ipinfo = cp.get('status/wan/ipinfo')
if ipinfo and isinstance(ipinfo, dict):
    ip = ipinfo.get('ip_address', 'unknown')
    gateway = ipinfo.get('gateway', 'unknown')
    cp.log(f'WAN IP: {ip} via {gateway}')
```

### REST
```
GET /api/status/wan/ipinfo
```

### Example Response
```json
{
  "success": true,
  "data": {
    "primary": "mdm-41949674",
    "gateway": "33.164.83.250",
    "ip_address": "33.164.83.249",
    "netmask": "255.255.255.252",
    "dns": ["10.177.0.34", "10.177.0.210"]
  }
}
```

### Related
- [ip6info](ip6info.md)
- [devices/{id}/status/ipinfo](devices/status.md)
