# WAN Dashboard
![image](https://github.com/user-attachments/assets/ca55cbc2-28fd-4851-be8d-5f63eef2d652)

## Features

- **Cumulative Traffic Graph**: Shows total download/upload across all WAN interfaces
- **Individual Interface Graphs**: Separate charts for each WAN interface (cellular modems, ethernet)
- **Real-time Updates**: Auto-refreshes every 3 seconds (configurable)
- **Interface Details**: Shows device info including SIM slots, carriers, and ports
- **Responsive Design**: Adapts to browser window size

## Interface Information

- **Cellular Modems**: Displays device ID, port, SIM slot, and carrier
- **Ethernet**: Shows device ID and port number
- **Router Name**: Dashboard title includes the router name

## Configuration

- **Update Interval**: Set `wan_dashboard_interval` in appdata (default: 3 seconds)
- **Port**: Set `wan_dashboard_web_port` in appdata to choose the web port. If not set, the app uses the first free port from 8000 and saves it there. The port in use is shown in the app log

## Access

- **NCM Remote Connect**: Use NCM to connect to `127.0.0.1` and the app's web port via HTTP
- **Local Access**: `http://<router_ip>:<port>`. LAN clients need a firewall zone forwarding rule from Primary LAN Zone to Router Zone to reach the app's web port

## Appdata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `wan_dashboard_interval` | No | Dashboard update interval in seconds. Default: 3 |
| `wan_dashboard_web_port` | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 and saves it here. Delete it to pick a port automatically again. |
| `wan_dashboard_port` | No | Deprecated. Older name for the web port, used only when `wan_dashboard_web_port` is not set. |

The startup log shows the port in use, for example `Bound port 8001 (discovered, saved to wan_dashboard_web_port)` followed by `Web server started on port 8001`. If `wan_dashboard_web_port` is set and that port is busy, the app retries for about 10 seconds and never moves to another port. If the value is not a number from 1 to 65535, or the port stays busy, the app stops itself and logs why. Fix or delete the field, then start the app.

To change the port for one router or a group, set `wan_dashboard_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection.
