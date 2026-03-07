# status/wan/devices/{device_id}/status

<!-- path: status/wan/devices/{device_id}/status -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / [devices](.) / status

---

Connection state, signal, and IP for a WAN device.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `connection_state` | string | `connected`, `disconnected`, `connecting` |
| `link_state` | string | `up`, `down`, `unknown` |
| `summary` | string | Human summary (`connected`, `unplugged`, etc.) |
| `ready` | string | Ready state or reason |
| `signal_strength` | string | Cellular signal % or `unknown` |
| `uptime` | float | Seconds connected (null if disconnected) |
| `ipinfo` | object | See sub-table |
| `ip6info` | object | See sub-table |
| `error_text` | string | Error message if any |
| `plugged` | boolean | Physical connection |
| `configured` | boolean | Config applied |
| `idle` | boolean | Idle state |
| `reason` | string | Failover reason (e.g. "Failover") |
| `idle_check` | object | See sub-table |
| `traffic_check` | object | See sub-table |
| `gps` | object | See sub-table |
| `cellular_health_score` | number | Health score (optional) |
| `cellular_health_category` | string | Health category (optional) |

**ipinfo**

| Field | Type | Description |
|-------|------|-------------|
| `gateway` | string | Gateway |
| `ip_address` | string | IP address |
| `netmask` | string | Netmask |
| `dns` | array | DNS servers |

**ip6info**

| Field | Type | Description |
|-------|------|-------------|
| `gateway` | string | IPv6 gateway |
| `ip_address` | string | IPv6 address |
| `prefix_len` | number | Prefix length |
| `dns` | array | IPv6 DNS servers |
| *(varies)* | * | Other IPv6 config when applicable |

**idle_check**

| Field | Type | Description |
|-------|------|-------------|
| `history` | array | History entries |
| `average` | number\|null | Average kbytes |
| `period` | number | Period seconds |
| `kbytes` | number | Kbytes threshold |
| `window` | number | Window seconds |
| `started` | boolean | Check started |

**traffic_check**

| Field | Type | Description |
|-------|------|-------------|
| `history` | array | History entries |
| `average` | number\|null | Average kbytes |
| `period` | number | Period seconds |
| `kbytes` | number | Kbytes |
| `window` | number | Window seconds |
| `started` | boolean | Check started |
| `wanted` | boolean | Wanted |
| `enabled` | boolean | Enabled |

**gps**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | GPS status (modems only; may include NMEA, fix) |

### SDK Example
```python
import cp
status = cp.get(f'status/wan/devices/{device_id}/status')
if status:
    conn = status.get('connection_state')
    signal = status.get('signal_strength')
    cp.log(f'{device_id}: {conn} signal {signal}')
```

### REST
```
GET /api/status/wan/devices/{device_id}/status
```

### Related
- [diagnostics](diagnostics.md) - Cellular signal details
- [info](info.md)
