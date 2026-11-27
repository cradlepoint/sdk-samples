<img width="1264" height="664" alt="image" src="https://github.com/user-attachments/assets/b9411a1a-a7fa-4e13-8654-b2dbee24ef31" />

## Features

- **Cumulative Traffic Graph**: Shows total download/upload across all WAN interfaces
- **Individual Interface Graphs**: Separate charts for each WAN interface (cellular modems, ethernet)
- **Real-time Updates**: The live chart refreshes every second, and the device list and the longer timeframes refresh every 5 seconds
- **Four Timeframes**: Live (last 5 minutes), 5-minute averages for 24 hours, hourly averages for 1 week, and daily averages for 1 year
- **Asset ID Summary**: Writes the average download and upload rate across all WAN interfaces to the router's Asset ID in NCM (can be turned off, see below)
- **Interface Details**: Shows device info including SIM slots, carriers, and ports
- **Responsive Design**: Adapts to browser window size

## Interface Information

- **Cellular Modems**: Displays device ID, port, SIM slot, and carrier
- **Ethernet**: Shows device ID and port number
- **Router Name**: Dashboard title includes the router name

## Configuration

- **Port**: Set `wan_dashboard_web_port` in appdata to choose the web port. If not set, the app uses port 8000, or the next free port up to 8100 if 8000 is busy, and saves it there only in that case. The port in use is shown in the app log

- **Asset ID summary**: Every 300 seconds the app writes the average of the last 300 seconds of traffic to the Asset ID, for example `↓ 12.3 Mbps, ↑ 1.4 Mbps`. Only interfaces that were connected during that period are counted, and an interface only counts once it has a full buffer of data. Set `wan_rate_disable` to turn this off. The other `wan_rate_*` fields below tune it
## Access

- **NCM Remote Connect**: Use NCM to connect to `127.0.0.1` and the app's web port via HTTP
- **Local Access**: `http://<router_ip>:<port>`. LAN clients need a firewall zone forwarding rule from Primary LAN Zone to Router Zone to reach the app's web port

## Appdata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `wan_dashboard_web_port` | No | Web UI port (1024-65535). If set, the app uses exactly this port. If not set, it uses port 8000, or the next free port up to 8100 if 8000 is busy, and saves it here only in that case. Delete it to pick a port automatically again. |

| `wan_rate_disable` | No | If this field exists, even with an empty value, the app does not write the Asset ID summary. Default: field absent, summary on. |
| `wan_rate_report_interval` | No | Seconds between Asset ID updates. Default: 300. Values below 60 are raised to 60, and a value that is not a whole number falls back to 300. |
| `wan_rate_buffer_size` | No | Seconds of traffic to average for each update. Default: 300. Values below 60 are raised to 60, and values above 300 act as 300 because the app keeps 300 seconds of live data. |
| `wan_rate_output_path` | No | Config path the summary is written to. Default: `/config/system/asset_id`. |

The startup log shows the port in use, for example `Default port 8000 in use; bound 8001 (saved to wan_dashboard_web_port)` followed by `Web server started on port 8001`. If `wan_dashboard_web_port` is set and that port is busy, the app retries for about 10 seconds and never moves to another port. If the value is not a number from 1024 to 65535, or the port stays busy, the app stops itself and logs why. Fix or delete the field, then start the app.

To change the port for one router or a group, set `wan_dashboard_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection.
