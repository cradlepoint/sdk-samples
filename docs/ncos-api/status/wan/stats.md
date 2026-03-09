# status/wan/stats

<!-- path: status/wan/stats -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / stats

---

Aggregate traffic statistics for the active WAN connection.

### Response Type
`object`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `in` | integer | Total bytes received |
| `out` | integer | Total bytes sent |
| `ipackets` | integer | Packets received |
| `opackets` | integer | Packets sent |
| `ierrors` | integer | Receive errors |
| `oerrors` | integer | Transmit errors |
| `idrops` | integer | Received packets dropped |
| `bps` | integer | Bytes per second (ingress) |
| `ibps` | integer | Ingress bytes/sec |
| `obps` | integer | Egress bytes/sec |
| `collisions` | integer | Collision count |
| `imcasts` | integer | Incoming multicast |
| `omcasts` | integer | Outgoing multicast |
| `noproto` | integer | Unknown protocol |
| `ts` | float | Timestamp (system uptime) |

### SDK Example
```python
import cp
stats = cp.get('status/wan/stats')
if stats and isinstance(stats, dict):
    in_mb = stats.get('in', 0) / (1024 * 1024)
    out_mb = stats.get('out', 0) / (1024 * 1024)
    cp.log(f'WAN traffic: {in_mb:.1f} MB in, {out_mb:.1f} MB out')
```

### REST
```
GET /api/status/wan/stats
```

### Example Response
```json
{
  "success": true,
  "data": {
    "bps": 0,
    "collisions": 0,
    "ibps": 0,
    "idrops": 0,
    "ierrors": 0,
    "imcasts": 0,
    "in": 4223948,
    "ipackets": 18133,
    "noproto": 0,
    "obps": 0,
    "oerrors": 0,
    "omcasts": 0,
    "opackets": 19840,
    "out": 6286105,
    "ts": 157861.749640768
  }
}
```

### Related
- [devices/{id}/stats](devices/stats.md) - Per-device stats
