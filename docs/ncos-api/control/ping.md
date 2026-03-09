# control/ping

<!-- path: control/ping -->
<!-- type: control -->
<!-- response: object -->

[control](../) / ping

---

Ping control: start, stop, status, results.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `start` | object | PUT to start; params in sub-table |
| `stop` | string | PUT to stop |
| `status` | string | Current state: running, done, stopped, error |
| `result` | string | Ping results |

**start (request body)**

| Field | Type | Description |
|-------|------|-------------|
| `host` | string | Hostname or IP |
| `timeout` | number | Timeout seconds (default 11) |
| `deadline` | string | Same as timeout |
| `num` | number | Number of pings (default 4) |
| `interval` | number | Seconds between pings (default 1) |
| `size` | number | Packet size (default 56) |
| `df` | string | Path MTU: do, want, dont |
| `srcaddr` | string | Source IP |
| `iface` | string | Interface/device |
| `family` | string | inet, inet6 |
| `fwmark` | string | Socket mark |
| `bind_ip` | boolean | Bind to interface IP |

### SDK Example
```python
import cp
# Start ping
cp.put('control/ping/start', {'host': '8.8.8.8', 'num': 4})
# Check status
status = cp.get('control/ping/status')
# Stop
cp.put('control/ping/stop', '')
# Get results
results = cp.get('control/ping/result')
```

### REST
```
PUT /api/control/ping/start
Body: {"host": "8.8.8.8", "num": 4}
GET /api/control/ping/status
PUT /api/control/ping/stop
GET /api/control/ping/result
```
