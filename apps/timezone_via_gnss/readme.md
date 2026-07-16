# timezone_via_gnss
Automatically sets the router's timezone based on its GNSS (GPS) position using the TimezoneDB API. Runs once on boot, determines the timezone offset from coordinates, applies it to the system clock, and saves the result to SDK appdata.

## How It Works

1. Waits for 120 seconds of uptime (allows GPS to acquire a fix)
2. Checks if timezone has already been set (exits if `timezone_offset` appdata exists)
3. Retrieves the TimezoneDB API key from SDK appdata
4. Waits for a valid GPS fix with latitude/longitude
5. Queries the TimezoneDB API for the UTC offset at those coordinates
6. Applies the offset to `config/system/timezone` (system clock setting)
7. Saves the offset to `timezone_offset` appdata (prevents re-running)
8. Optionally notifies via description field, asset_id, or NCM alert

## SDK Appdata Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `timezonedb_api_key` | Yes | Your TimezoneDB API key (get one at [timezonedb.com](https://timezonedb.com)) |
| `timezone_offset` | No (auto-set) | Stored result — if present, app exits immediately |
| `timezone_notify` | No | Notification method(s): `desc`, `asset_id`, `alert` (comma-separated) |

### Notification Options

Set `timezone_notify` to one or more of:
- `desc` — Write result to device description
- `asset_id` — Write result to asset ID field
- `alert` — Send NCM alert with the result

Example: `desc,alert` will update description AND send an alert.

## One-Shot Behavior

This app runs once and exits:
- If `timezone_offset` is already set in appdata, the app exits immediately
- `restart = false` in package.ini means it won't run again until next reboot
- To re-run, delete the `timezone_offset` appdata field and reboot

## Timezone Format

The offset is stored as a string like `5`, `-8`, `5:30`, `-3:30` representing hours (and minutes) from UTC. The app validates against all standard UTC offsets.

## Error Handling

- If API key is missing: retries every 60 seconds until configured
- If no GPS fix: retries every 60 seconds until lock acquired
- If TimezoneDB API fails: retries up to 5 times, then defaults to UTC (+0)
- If timezone cannot be determined: sets UTC and notes manual configuration needed

## Requirements

- Router firmware 7.26 or later
- GNSS antenna connected with GPS enabled
- TimezoneDB API key (free tier: 1 request/second)
- Internet connectivity for API call
- `requests` library (available system-wide on cppython)
