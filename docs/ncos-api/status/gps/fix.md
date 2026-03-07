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
| `degree` | number | Degrees |
| `minute` | number | Minutes |
| `second` | number | Seconds |
