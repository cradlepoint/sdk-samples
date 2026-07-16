# iperf3
Runs iPerf3 bandwidth tests to a user-defined server and writes the results to the router's `asset_id` field. The iPerf3 binary is bundled with the app — no download required.

## How It Works

1. On startup, the app looks for a bundled `iperf3-arm64v8` binary in the app directory
2. Reads the target server from SDK appdata (`iperf3_server`)
3. Runs an upload test and a download test (using `-R` flag)
4. Writes results to `config/system/asset_id`, logs them, and sends an NCM alert
5. Registers a callback — when `asset_id` is cleared, it triggers a new test

## SDK Appdata Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `iperf3_server` | Yes | Hostname or IP of the iPerf3 server to test against |

Set this in System > SDK Data. If not configured, the app will create the field and log a reminder.

## Triggering a Test

The app runs a test automatically on startup. To trigger additional tests:

- **From NCM**: Clear the Asset ID field in the Devices grid
- **From NCM API**: PUT an empty string to the router's `asset_id`:
  ```json
  {"asset_id": ""}
  ```
- **From router CLI**: `put config/system/asset_id ""`

When the `asset_id` is cleared, the callback fires and runs a new test.

## Results Format

Results are written to `asset_id` in the format:

```
85.23Mbps Download 42.11Mbps Upload
```

Results are also:
- Logged to the router syslog
- Sent as an NCM alert

## Retrieving Results

- **NCM Devices grid**: Check the Asset ID column
- **NCM API v2**: GET `/routers/{router_id}/` and read the `asset_id` field
- **Router CLI**: `get config/system/asset_id`

## Requirements

- Router firmware 7.26 or later
- An iPerf3 server reachable from the router's WAN
- Network connectivity to the iPerf3 server on port 5201 (default)

## Notes

- The bundled binary (`iperf3-arm64v8`) is for ARM64 routers — compatible with all current Cradlepoint models
- Each test has a 60-second timeout
- The app runs both upload and download tests sequentially
- Customize result handling by editing the `process_results()` function
