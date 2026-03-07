# status/dhcpd

<!-- path: status/dhcpd -->
<!-- type: status -->
<!-- response: object -->

[status](../) / dhcpd

---

DHCP server (LAN) lease status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `leases` | array | Lease objects, see sub-table |

**leases[]**

| Field | Type | Description |
|-------|------|-------------|
| `client_id` | string | DHCP client ID |
| `hostname` | string | Client hostname |
| `mac` | string | Client MAC |
| `ip_address` | string | Assigned IP |
| `expire` | number | Lease expiry (seconds) |
| `iface` | string | Interface (e.g. guestlan4) |
| `iface_type` | string | wireless, ethernet, etc. |
| `ssid` | string | WiFi SSID (if wireless) |
| `network` | string | Network name |

### SDK Example
```python
import cp
dhcpd = cp.get('status/dhcpd')
if dhcpd:
    leases = dhcpd.get('leases', [])
    cp.log(f'DHCP leases: {len(leases)}')
```

### REST
```
GET /api/status/dhcpd
```
