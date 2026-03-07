# status/wan/policies

<!-- path: status/wan/policies -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / policies

---

WAN policy engine state. Each policy (FailoverFailback, DualSIM, SWANS, etc.) has enabled flag and current state.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `policies` | object | Policy name → per-policy object, see sub-table |
| `primary` | string | Current primary device ID |

**Per-policy object (policies.{name})**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Policy enabled |
| `state` | string\|null | Policy state (e.g. connected, idle) |

### Policy Examples
- `FailoverFailback` - Failover/failback state
- `DualSIM` - Dual SIM management
- `SWANS` - Smart WAN Selection
- `Affinity` - Traffic affinity rules
- `OnDemand` - On-demand connection

### SDK Example
```python
import cp
policies = cp.get('status/wan/policies')
if policies:
    prim = policies.get('primary')
    pols = policies.get('policies', {})
    ff = pols.get('FailoverFailback', {})
    cp.log(f'Primary: {prim}, FailoverFailback: {ff.get("state")}')
```

### REST
```
GET /api/status/wan/policies
```

### Example Response (partial)
```json
{
  "success": true,
  "data": {
    "policies": {
      "FailoverFailback": {"enabled": true, "state": "connected"},
      "SWANS": {"enabled": false, "state": "idle"},
      "DualSIM": {"enabled": true, "state": null}
    },
    "primary": "mdm-41949674"
  }
}
```
