# Power Dashboard

A comprehensive real-time power usage monitoring application for Cradlepoint routers that tracks current, total energy consumption, and voltage with a professional web interface.  Optional power indicator message in asset ID.  

[Download the built app here!](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/power_dashboard.v1.3.0.tar.gz)  

<img width="1392" height="808" alt="image" src="https://github.com/user-attachments/assets/1540199c-b2b8-4b94-9551-5baf1ccd0c11" />
<img width="1392" height="837" alt="image" src="https://github.com/user-attachments/assets/53f9418c-7600-42ab-bcd6-fe923966a667" />

## Known Supported Devices:
**Total (W), Voltage (V), Current (A)**: R980, S400  
**Total (W) ONLY**: R920, R1900, S700, IBR1700, IBR600C, E-series  
**NOT SUPPORTED**: IBR900

## Features

- **Real-time Power Monitoring**: Current (A), Total Energy (Wh), Voltage (V) tracking
- **Interactive Dashboard**: Web interface with live charts and statistics
- **Historical Data**: 30 days retention with configurable polling intervals
- **Min/Max Tracking**: Historical minimum and maximum values with timestamps
- **CSV Export**: Download complete historical data
- **Responsive Design**: Works on desktop and mobile devices
- **Auto-refresh**: Updates every 30 seconds without page reload
- **NCM Visibility**: Optional power indicator message in asset ID field in NCM devices grid
- **Voltage Alerts**: Automatic alerts when voltage crosses thresholds

## Installation

1. **Upload Application**: Upload the `power_dashboard.tar.gz` file to the Tools page in NetCloud Manager
2. **Assign to Groups**: Assign the application to the desired router groups
3. **Application Deployment**: The application will automatically deploy and start on assigned routers

## Access Methods

### Local Access
- **Direct Browser**: Navigate to `http://[router-ip-address]:8000` in your web browser
- **PrimaryLAN Zone Forwarding**: Forward the PrimaryLAN zone to the Router zone to enable local network access

### Remote Access - NetCloud Manager
- **Remote Connect LAN Manager**: 
  - **Protocol**: HTTP
  - **Host**: 127.0.0.1
  - **Port**: 8000

## Configuration

### Appdata Fields

Use these appdata keys to configure behavior:

- `power_dashboard_interval`: Polling interval in seconds. Default: 300 (5 minutes)

Use these appdata keys to configure voltage indicator "lights" in asset ID (🟢 12.17V | 0.44A | 5.34W):

- `power_dashboard_lights`: If present (even empty), enables writing a voltage indicator message
- `power_dashboard_lights_interval`: Seconds between indicator writes. Default: 300
- `power_dashboard_lights_path`: Config path to write the message. Default: `config/system/asset_id`
- `power_dashboard_high`: High voltage threshold (V). Default: 12.1
- `power_dashboard_med`: Medium voltage threshold (V). Default: 11.5 (below is low)

Indicator in message: High `🟢`, Medium `🟡`, Low `🔴`, No data (None/0V) `⚫`.

### Voltage Alerts

The application automatically sends alerts via `cp.alert()` when voltage crosses thresholds:
- **On startup**: Alerts if voltage is not high (low or medium only)
- **During operation**: Alerts once each time voltage changes between high/medium/low thresholds

Example alert messages:
- `Power Dashboard: Low voltage alert - 11.20V (below 11.5V)`
- `Power Dashboard: Medium voltage alert - 11.80V (below 12.1V)`
- `Power Dashboard: Voltage dropped to medium - 11.85V (below 12.1V)`
- `Power Dashboard: Voltage improved to medium - 11.60V`
- `Power Dashboard: Voltage returned to high - 12.15V`

### Data Retention

- **In-Memory**: Last 24 hours of data for fast web interface access
- **On-Disk**: 30 days of historical data
- **Automatic Calculation**: Data points calculated based on polling interval
  - 5-minute intervals: 8,640 points for 30 days
  - 1-minute intervals: 43,200 points for 30 days
  - 10-minute intervals: 4,320 points for 30 days

