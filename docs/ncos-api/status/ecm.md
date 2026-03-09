# status/ecm

<!-- path: status/ecm -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / ecm

---

NetCloud / ECM (Enterprise Connectivity Manager) connection status.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | connected, disconnected |
| `managed` | boolean | Managed by NCM |
| `error` | string\|null | Error message |
| `client_id` | integer | NCM client ID |
| `ts` | float | Timestamp |
| `event_triggers` | array | See [ecm/event_triggers.md](ecm/event_triggers.md) |
| `data_usage_in` | number | Bytes in this period |
| `data_usage_out` | number | Bytes out this period |
| `data_usage_period` | number | Period duration (seconds) |
| `recent_activity` | array | `[seconds_since, message]` |
| `retry_timer` | null\|object | Retry state |
| `retry_delay` | null\|number | Retry delay |
| `sync` | string | e.g. "ready" |
| `last_patch` | array | See [ecm/last_patch.md](ecm/last_patch.md) |
| `server_host_redirect` | string | Redirect host |
| `server_port_redirect` | number | Redirect port |
| `uptime` | number | Session uptime seconds |
| `rollback` | null\|object | Rollback state |
| `info` | object | `{Account, Group}` |
| `client_usage_monitoring` | boolean | Client usage monitoring enabled |

### SDK Example
```python
import cp
ecm = cp.get('status/ecm')
if ecm:
    cp.log(f'ECM: {ecm.get("state")} managed={ecm.get("managed")}')
```

### REST
```
GET /api/status/ecm
```

### Breakout docs (in ecm/)
- [ecm/event_triggers.md](ecm/event_triggers.md) – event_triggers[] (13 fields)
- [ecm/last_patch.md](ecm/last_patch.md) – last_patch[] config (depth 3)
