# status/system

<!-- path: status/system -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / system

---

System status: boot ID, service manager, and service states.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `bootid` | string | Unique boot identifier |
| `smanager` | object | `{startup: {starting, started, svcs_started}}` |
| `services` | object | Service name to state |
| `accessories` | array | See sub-table |
| `rtc` | boolean | RTC present |
| `uptime` | number | Uptime seconds |
| `load_avg` | object | 1min, 5min, 15min |
| `cpu` | object | user, nice, system |
| `memory` | object | See [system/memory.md](system/memory.md) |
| `threads` | array | name, ident |
| `time` | number | Unix timestamp |
| `temperature` | number | Router temp C |
| `modem` | object | Modem UID to temp |
| `modem_temperature` | number | Primary modem temp |
| `wan_signal_strength` | number | 0 to 100 |
| `tz` | string | Timezone string |
| `storage` | object | health, slc_health |
| `poe_pse` | object | power_budget, etc |
| `ntp` | object | mode, sync_age, last_server |
| `apps` | array | Internal apps |
| `sdk` | object | See [system/sdk.md](system/sdk.md) |
| `sensors` | object | level, day |
| `boot` | string | e.g. done |
| `serial` | object | status, serial_ip |
| `console` | object | status |
| `commands` | boolean | Commands available |
| `interrupts` | number | Interrupt count |
| `context_switches` | number | Context switch count |
| `debug_info` | object | See [system/debug_info.md](system/debug_info.md) |
| `internal_svcs` | object | running |
| `fw_upgrade_timeout` | boolean | Upgrade timeout flag |

**accessories[]**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Accessory type |
| `desc` | string | Description |
| `present` | boolean | Present |

### SDK Example
```python
import cp
sys = cp.get('status/system')
if sys:
    bootid = sys.get('bootid')
    svcs = sys.get('services', {})
    cp.log(f'Boot: {bootid}, services: {len(svcs)}')
```

### REST
```
GET /api/status/system
```

### Breakout docs (in system/)
- [system/memory.md](system/memory.md) – Memory object (45 fields)
- [system/sdk.md](system/sdk.md) – SDK service and apps
- [system/debug_info.md](system/debug_info.md) – ECM/debug nested structure

### Related
- [product_info](product_info.md) – Product info
