# status/tcpdump

<!-- path: status/tcpdump -->
<!-- type: status -->
<!-- response: object -->

[status](../) / tcpdump

---

Packet capture status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `running` | object\|null | See sub-table (when active) |
| `interface` | string\|null | Capture interface |
| `args` | string\|null | Capture arguments |

**running**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Running capture info (pid, bytes_captured, etc.) |

### SDK Example
```python
import cp
tcpdump = cp.get('status/tcpdump')
if tcpdump:
    cp.log(f'tcpdump: running={tcpdump.get("running")} iface={tcpdump.get("interface")}')
```

### REST
```
GET /api/status/tcpdump
```
