# clients
Reports connected LAN client IP addresses and MAC addresses to a configurable router status field. Useful for monitoring which devices are connected to the router's LAN.

## How It Works

The app polls `cp.get_lan_clients()` every 60 seconds to retrieve all connected IPv4 clients. It formats the results as a summary string and writes it to a configurable router field (defaults to `config/system/asset_id`).

## Output Format

The app writes a string in the following format:

```
3 Clients: 192.168.0.10 (AA:BB:CC:DD:EE:01), 192.168.0.11 (AA:BB:CC:DD:EE:02), 192.168.0.12 (AA:BB:CC:DD:EE:03)
```

The count of clients is shown first, followed by each client's IP address and MAC address in parentheses.

## SDK Appdata Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `clients` | No | `config/system/asset_id` | Router config/status path where results are written |

To change the output field, set SDK Data field `clients` to any valid router path, for example `config/system/description`.

## Polling Interval

The app polls every 60 seconds. Each poll retrieves the current list of connected LAN clients and overwrites the previous value in the configured field.

## Viewing Results

- On the router: `get config/system/asset_id` (or your configured path)
- In NCM: Check the Asset ID column in the Devices list (if using default path)
- Via NCM API: GET the router resource and read the `asset_id` field

## Requirements

- Router firmware 7.26 or later
- Connected LAN clients (wired or wireless)
