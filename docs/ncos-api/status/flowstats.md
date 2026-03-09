# status/flowstats

<!-- path: status/flowstats -->
<!-- type: status -->
<!-- response: object -->

[status](../) / flowstats

---

Flow statistics (per-destination packet/byte counts).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ipdst` | object | See sub-table |

**ipdst**

| Field | Type | Description |
|-------|------|-------------|
| `destinations` | array | See sub-table |
| `totalpkts` | integer | Total packets |
| `totaldsts` | integer | Total destinations |

**ipdst.destinations[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Per-destination stats (address, packets, bytes, etc.) |

### SDK Example
```python
import cp
fs = cp.get('status/flowstats')
if fs:
    ipdst = fs.get('ipdst', {})
    cp.log(f'Flow stats: {ipdst.get("totalpkts")} pkts')
```

### REST
```
GET /api/status/flowstats
```
