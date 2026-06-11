# status/gps – fix

<!-- path: status/gps/fix -->
<!-- type: status -->

[status](../) / [gps](../gps.md) / fix

---

GPS fix data (10 fields, latitude/longitude add depth 3). Returned as `status/gps` → `fix`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `latitude` | object | See sub-table |
| `longitude` | object | See sub-table |
| `satellites` | integer | Satellite count |
| `lock` | boolean | Fix acquired |
| `altitude_meters` | float | Altitude |
| `age` | float | Fix age (seconds) |
| `time` | number | Time value |
| `from_sentence` | string\|null | Source NMEA sentence |
| `ground_speed_knots` | number\|null | Ground speed |
| `heading` | number\|null | Heading degrees |

**fix.latitude / fix.longitude**

| Field | Type | Description |
|-------|------|-------------|
| `degree` | integer | Degrees (e.g. `43`, `-116`). Negative = South/West |
| `minute` | integer | Minutes (e.g. `40`) |
| `second` | float | Seconds (e.g. `23.2175`) |

**Important:** DMS values must be **numbers** (int/float), not strings. The router's internal WPC client does arithmetic on these fields — string values cause `'<' not supported between 'str' and 'int'` errors. The hardware GPS daemon writes strings (e.g. `"43.0"`) but when injecting via `cp.put()`, use numeric types.
