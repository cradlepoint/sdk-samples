# control/ecm

<!-- path: control/ecm -->
<!-- type: control -->
<!-- response: object -->

[control](../) / ecm

---

ECM (NetCloud / NCM) control: register, start, stop, restart.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `register` | object | Registration params |
| `register.username` | string | Username |
| `register.password` | string | Password |
| `register.token_id` | string | Token ID |
| `register.token_secret` | string | Token secret |
| `stop` | boolean | PUT true to stop ECM |
| `start` | boolean | PUT true to start ECM |
| `restart` | null | PUT to restart |
| `reset_timers` | null | Reset timers |
| `enable_legacy` | boolean | Legacy mode |
| `server_stopped` | boolean | Server stopped flag |
| `cert` | string\|null | Certificate |

### SDK Example
```python
import cp
# Start ECM
cp.put('control/ecm/start', True)
# Stop ECM
cp.put('control/ecm/stop', True)
# Restart
cp.put('control/ecm/restart', None)
```

### REST
```
PUT /api/control/ecm/start
Body: true
```

### Related
- [status/ecm](../status/ecm.md) - ECM status
