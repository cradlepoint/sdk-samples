# status/dhcp

<!-- path: status/dhcp -->
<!-- type: status -->
<!-- response: object -->

[status](../) / dhcp

---

DHCP client status (WAN). Keyed by device ID (e.g. mdm-41949674).

### Fields (top-level)

Object keyed by device ID (e.g. `mdm-41949674`).

**Per-device object**

| Field | Type | Description |
|-------|------|-------------|
| `ipinfo` | object | See sub-table |
| `dns` | array | DNS server addresses |
| `event` | string | RENEW, BOUND, etc. |

**ipinfo**

| Field | Type | Description |
|-------|------|-------------|
| `gateway` | string | Gateway address |
| `ip_address` | string | Assigned IP |
| `subnet_mask` | string | Subnet mask |

### SDK Example
```python
import cp
dhcp = cp.get('status/dhcp')
if dhcp:
    for dev, d in dhcp.items():
        ip = d.get('ipinfo', {}).get('ip_address')
        cp.log(f'{dev}: {ip} event={d.get("event")}')
```

### REST
```
GET /api/status/dhcp
```
