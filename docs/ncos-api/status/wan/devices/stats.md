# status/wan/devices/{device_id}/stats

<!-- path: status/wan/devices/{device_id}/stats -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / [devices](.) / stats

---

Per-device traffic statistics.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `in` | integer | Bytes received |
| `out` | integer | Bytes sent |
| `ipackets` | integer | Packets received |
| `opackets` | integer | Packets sent |
| `ierrors` | integer | Receive errors |
| `oerrors` | integer | Transmit errors |
| `idrops` | integer | Receive drops |
| `odrops` | integer | Transmit drops |
| `multicast` | integer | Multicast packets |
| `collisions` | integer | Collisions |

### SDK Example
```python
import cp
stats = cp.get(f'status/wan/devices/{device_id}/stats')
if stats:
    in_mb = stats.get('in', 0) / (1024 * 1024)
    out_mb = stats.get('out', 0) / (1024 * 1024)
    cp.log(f'{device_id}: {in_mb:.1f} MB in, {out_mb:.1f} MB out')
```

### REST
```
GET /api/status/wan/devices/{device_id}/stats
```

### Related
- [status/wan/stats](../stats.md) - Aggregate WAN stats
