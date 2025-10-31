# WAN Dashboard

[Download the built-app here!](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/wan_dashboard.v1.3.0.tar.gz)

<img width="1257" height="793" alt="image" src="https://github.com/user-attachments/assets/ca55cbc2-28fd-4851-be8d-5f63eef2d652" />

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
- **Port**: Set `wan_dashboard_port` in appdata (default: 8000)

## Access

- **NCM Remote Connect**: Use NCM to connect to `127.0.0.1:8000` (or your configured port) via HTTP
- **Local Access**: `http://router-ip:8000` (or your configured port)
