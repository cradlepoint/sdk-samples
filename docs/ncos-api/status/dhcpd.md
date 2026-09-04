# status/dhcpd

<!-- path: status/dhcpd -->
<!-- type: status -->
<!-- response: object -->

[status](../) / dhcpd

---

DHCP server (LAN) lease status.

**Returns `null` when the LAN DHCP server is disabled** (`config/lan/0/dhcpd/enabled = false`)
— not `{'leases': []}`. Always `cp.get('status/dhcpd') or {}` before `.get('leases', [])`.
An app that infers something about client devices from an empty lease list should check that
the router is actually the DHCP server for them. `/api/dtd/status/dhcpd` does not exist
(returns `{"exception": "key", "key": "status"}`), so field types can only be confirmed from
a live response with leases present.

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
