# speed_limit

Monitors vehicle speed via GPS and sends an alert when a speed limit violation ends, including start/end timestamps, start/end locations, and maximum speed reached.

## Behavior

1. Reads GPS fix data every 2 seconds
2. Converts `ground_speed_knots` to MPH (× 1.15078)
3. When speed exceeds the configured limit, records the timestamp and lat/long
4. Continues monitoring and tracks maximum speed during the violation
5. When speed drops back below the limit, sends an NCM alert with:
   - Max speed during the violation
   - Start timestamp and location
   - End timestamp and location

## Example Alert

```
Speed violation: max 112.3 MPH (limit 100 MPH). Start: 2025-06-12 14:05:22 at 43.670894,-116.293571. End: 2025-06-12 14:08:47 at 43.682110,-116.287403.
```

## Appdata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `speed_limit_mph` | No | Speed limit in MPH. Default: 100 |

## Requirements

- GPS must be enabled and have a fix
- Router must have a GPS antenna connected
