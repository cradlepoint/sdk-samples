# status/lldp

<!-- path: status/lldp -->
<!-- type: status -->
<!-- response: object -->

[status](../) / lldp

---

LLDP neighbor discovery.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `neighbors` | array | See sub-table |
| `chassis` | object | See sub-table |
| `daemon_config` | object | See sub-table |
| `ifaces` | array | See sub-table |
| `power_requests` | array | See sub-table |

**chassis**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Chassis info |

**daemon_config**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Daemon configuration |

**neighbors[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | LLDP neighbor entry (chassis, port, etc.) |

**ifaces[]**

| Field | Type | Description |
|-------|------|-------------|
| `iface` | string | Interface name |
| `mac` | string | MAC address |
| `mode` | string | lan, wan, etc. |

**power_requests[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Power request entry |

### SDK Example
```python
import cp
lldp = cp.get('status/lldp')
if lldp:
    n = lldp.get('neighbors', [])
    cp.log(f'LLDP neighbors: {len(n)}')
```

### REST
```
GET /api/status/lldp
```
