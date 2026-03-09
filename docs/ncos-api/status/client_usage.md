# status/client_usage

<!-- path: status/client_usage -->
<!-- type: status -->
<!-- response: object -->

[status](../) / client_usage

---

Client usage stats.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Client usage monitoring enabled |
| `stats` | array | Per-client stats, see sub-table |

**stats[] (per entry)**

| Field | Type | Description |
|-------|------|-------------|
| `mac` | string | Client MAC |
| `ssid` | string | SSID |
| `name` | string | Client name |
| `network` | string | Network |
| `type` | string | Client type |
| `ip` | string | IP address |
| `up_bytes` | integer | Bytes uploaded |
| `up_packets` | integer | Packets uploaded |
| `up_delta` | integer | Upload delta |
| `down_bytes` | integer | Bytes downloaded |
| `down_packets` | integer | Packets downloaded |
| `down_delta` | integer | Download delta |
| `last_time` | number | Last activity time |
| `first_time` | number | First seen time |
| `connect_time` | number | Connect time |
| `app_list` | array | See sub-table |

**stats[].app_list[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | App identifier or usage entry (when app visibility enabled) |

### SDK Example
```python
import cp
cu = cp.get('status/client_usage')
if cu:
    cp.log(f'Client usage: enabled={cu.get("enabled")} stats={len(cu.get("stats", []))}')
```

### REST
```
GET /api/status/client_usage
```
