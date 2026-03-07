# status/lan

<!-- path: status/lan -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / lan

---

LAN status: stats, clients, networks, UUID mapping.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `stats` | object | See sub-table |
| `clients` | array | See sub-table |
| `uuid` | object | LAN UUID to iface |
| `networks` | object | See [lan/networks.md](lan/networks.md) |
| `devices` | object | See [lan/devices.md](lan/devices.md) |

**stats**

| Field | Type | Description |
|-------|------|-------------|
| `bps` | number | Bytes per second |
| `ibps` | number | Ingress bytes/sec |
| `obps` | number | Egress bytes/sec |
| `in` | integer | Bytes in |
| `out` | integer | Bytes out |
| `ipackets` | integer | Packets in |
| `opackets` | integer | Packets out |
| `ts` | number | Timestamp |
| `collisions` | integer | Collisions |
| `idrops` | integer | Drops |

**clients[]**

| Field | Type | Description |
|-------|------|-------------|
| `mac` | string | Client MAC |
| `ip_address` | string | Client IP |

**uuid.{lan_uuid}**

| Field | Type | Description |
|-------|------|-------------|
| `iface` | string | Interface name (primarylan3, guestlan4) |

### SDK Example
```python
import cp
lan = cp.get('status/lan')
if lan:
    clients = lan.get('clients', [])
    cp.log(f'LAN clients: {len(clients)}')
```

### REST
```
GET /api/status/lan
```

### Breakout docs (in lan/)
- [lan/networks.md](lan/networks.md) – networks.{name} object (depth 3)
- [lan/devices.md](lan/devices.md) – devices.{device_id} object
