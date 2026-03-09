# status/wan/ip6info

<!-- path: status/wan/ip6info -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / ip6info

---

IPv6 configuration for the primary WAN. Empty `{}` when IPv6 is disabled or not assigned.

### Fields (when populated)

| Field | Type | Description |
|-------|------|-------------|
| `primary` | string | Device ID providing this IP info |
| `ip6_address` | string | WAN IPv6 address |
| `gateway` | string | IPv6 gateway |
| `prefix_length` | number | Prefix length |
| `dns` | array | IPv6 DNS servers |

### SDK Example
```python
import cp
ip6info = cp.get('status/wan/ip6info')
if ip6info and isinstance(ip6info, dict) and ip6info:
    cp.log(f'IPv6: {ip6info}')
```

### REST
```
GET /api/status/wan/ip6info
```

### Example Response
```json
{"success": true, "data": {}}
```

### Related
- [ipinfo](ipinfo.md)
