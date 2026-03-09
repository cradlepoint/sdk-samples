# status/stats

<!-- path: status/stats -->
<!-- type: status -->
<!-- response: object -->

[status](../) / stats

---

Historical stats: usage, failover, wan_state_history, signal_history.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `usage` | object | See sub-table |
| `failover` | object | See sub-table |
| `wan_state_history` | object | See sub-table |
| `signal_history` | object | See sub-table |

**wan_state_history**

| Field | Type | Description |
|-------|------|-------------|
| `raw_history` | object | See sub-table |
| *(varies)* | * | Other history data |

**wan_state_history.raw_history**

| Field | Type | Description |
|-------|------|-------------|
| `states` | array | See sub-table |

**wan_state_history.raw_history.states[]** (array: `[device_id, state_code, timestamp, state_string]`)

| Index | Type | Description |
|-------|------|-------------|
| 0 | string | WAN device ID |
| 1 | number | State code (0=Unready, 2=Connected, etc.) |
| 2 | number | Epoch timestamp |
| 3 | string | State label (Unready, Failover, Always On, etc.) |

**signal_history**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Signal strength history by device |

**usage**

| Field | Type | Description |
|-------|------|-------------|
| `wan_in` | array | Inbound bytes/sec samples |
| `wan_out` | array | Outbound bytes/sec samples |
| `lan_in` | array | LAN inbound samples |

**usage.wan_in[] / wan_out[] / lan_in[]** (array of numbers)

| Index | Type | Description |
|-------|------|-------------|
| * | number | Bytes/sec or sample value |

**failover**

| Field | Type | Description |
|-------|------|-------------|
| `states` | array | See sub-table |
| `sample_rate` | number | Sample rate |
| `sample_size` | number | Sample size |

**failover.states[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Failover state sample (device, state, timestamp) |

### SDK Example
```python
import cp
stats = cp.get('status/stats')
if stats:
    usage = stats.get('usage', {})
    wan_in = usage.get('wan_in', [])
    cp.log(f'Stats: {len(wan_in)} wan_in samples')
```

### REST
```
GET /api/status/stats
```
