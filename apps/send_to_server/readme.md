# send_to_server
Collects data from configurable NCOS API paths and POSTs it as JSON to a remote server at a configurable interval. All settings (server URL, data fields, and interval) are stored in SDK appdata.

## How It Works

1. Reads configuration from SDK appdata field `send_to_server`
2. For each field in the payload configuration, calls `cp.get(path)` to read the data
3. POSTs the collected data as JSON to the configured server URL
4. Waits for the configured interval, then repeats

## SDK Appdata Configuration

The app stores its configuration in a single SDK appdata field named `send_to_server` as a JSON string:

```json
{
    "server_url": "https://httpbin.org/post",
    "interval": 10,
    "payload": {
        "hostname": "config/system/system_id",
        "mac": "status/product_info/mac0",
        "serial_number": "status/product_info/manufacturing/serial_num",
        "gps": "status/gps/fix"
    }
}
```

| Field | Description |
|-------|-------------|
| `server_url` | URL to POST data to |
| `interval` | Seconds between POST requests |
| `payload` | Map of field names to NCOS API paths |

### Payload Keys

Each key in `payload` becomes a field name in the JSON POST body. The value is the NCOS API path to read. You can add any valid `status/` or `config/` path.

## Default Behavior

If no appdata is configured, the app saves a default configuration and uses:
- Server: `https://httpbin.org/post` (test echo server)
- Interval: 10 seconds
- Payload: hostname, MAC, serial number, GPS fix

## Sample POST Body

```json
{
    "hostname": "MyRouter",
    "mac": "00:30:44:3B:38:77",
    "serial_number": "WA1234567",
    "gps": {"lock": true, "latitude": {...}, "longitude": {...}}
}
```

## Requirements

- Router firmware 7.26 or later
- Network connectivity to the target server
- `requests` library (available system-wide on cppython)

## Notes

- The test server `httpbin.org` echoes back what you send — useful for debugging
- For production, point `server_url` to your own data collection endpoint
- GPS data requires a GPS antenna and lock
