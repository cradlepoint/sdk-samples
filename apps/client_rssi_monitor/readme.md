# client_rssi_monitor
Monitors connected WiFi clients and reports their signal strength (RSSI), connection mode, bandwidth, and TX rate to the router's `asset_id` field. Useful for tracking wireless client performance from NCM.

## How It Works

The app polls every 30 seconds and:

1. Retrieves the list of connected WLAN clients (`status/wlan/clients`)
2. Matches clients against DHCP leases to get hostnames and SSIDs
3. Enriches each client with radio details (mode, bandwidth, TX rate, RSSI, connection time)
4. Writes a summary string to `config/system/asset_id`

The asset_id field is visible in NCM, making it easy to monitor client signal quality remotely.

## Output Format

The app writes a formatted string to `asset_id` grouped by SSID:

```
MyNetwork (laptop: 802.11ac, 80 Mhz, 866 Mbps, 5 Ghz, -42 dBm, 1:23:45 | phone: 802.11ax, 40 MHz, 287 Mbps, 5 Ghz, -55 dBm, 0:10:22)
```

Each client entry includes:
- **Identifier** — hostname (if available) or MAC address
- **Mode** — 802.11b/g/n/ac/ax
- **Bandwidth** — 20/40/80/160 MHz
- **TX Rate** — transmit rate in Mbps
- **Band** — 2.4 or 5 GHz
- **RSSI** — signal strength in dBm
- **Time** — connection duration (H:MM:SS)

## Retrieve Results via NCM API

Use an HTTP GET request to `https://www.cradlepointecm.com/api/v2/routers/{router_id}/` with your NCM API keys. The `asset_id` field contains the latest client RSSI summary.

## Configuration

No SDK appdata fields are required. The app runs automatically with a 30-second polling interval.
