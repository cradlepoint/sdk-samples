# status/gps

<!-- path: status/gps -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / gps

---

GPS fix, position, and device NMEA data.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `fix` | object | See [gps/fix.md](gps/fix.md) |
| `state` | integer | GPS state |
| `nmea` | array | NMEA sentences |
| `lastpos` | object | See sub-table |
| `connections` | object | Connection state (varies) |
| `schedule` | object | Schedule config (varies) |
| `ploop` | object | Poll loop state (varies) |
| `devices` | object | See sub-table |

**lastpos**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | number | Timestamp |
| `latitude` | number | Latitude |
| `longitude` | number | Longitude |
| `age` | number | Age |

**devices.{mdm_uid}**

| Field | Type | Description |
|-------|------|-------------|
| `current_nmea` | array | NMEA sentences (array of strings) |

### SDK Example
```python
import cp
gps = cp.get('status/gps')
if gps:
    fix = gps.get('fix', {})
    cp.log(f'GPS lock={fix.get("lock")} sats={fix.get("satellites")}')
```

### REST
```
GET /api/status/gps
```

### Breakout docs (in gps/)
- [gps/fix.md](gps/fix.md) – fix object (10 fields, latitude/longitude depth 3)
