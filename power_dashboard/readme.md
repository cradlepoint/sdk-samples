# Power Dashboard

A comprehensive real-time power usage monitoring application for Cradlepoint routers that tracks current, total energy consumption, and voltage with a professional web interface.  Optional power indicator message in asset ID.  

[Download the built app here!](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/power_dashboard.v1.4.0.tar.gz)  

<img width="1334" height="808" alt="image" src="https://github.com/user-attachments/assets/bcf7ae9a-0194-4db1-a7e6-a7e6a54d89d3" />
<img width="1334" height="849" alt="image" src="https://github.com/user-attachments/assets/1963d7be-d660-4078-9b22-6e0339f9cbd5" />

## Known Supported Devices:
**Total (W), Voltage (V), Current (A)**: R980, S400  
**Total (W), Voltage (V)**: R920, R1900  
**Total (W) ONLY**: S700, IBR1700, IBR600C, E3000    
**NOT SUPPORTED**: IBR900  

## Features

- **Real-time Power Monitoring**: Current (A), Total Energy (W), Voltage (V) tracking
- **Interactive Dashboard**: Web interface with live charts and statistics
- **Live Mode**: Real-time power monitoring with 1-second polling (separate from regular data collection)
- **Historical Data**: 30 days retention with configurable polling intervals
- **Min/Max Tracking**: Historical minimum and maximum values with timestamps
- **CSV Export**: Download complete historical data
- **Responsive Design**: Works on desktop and mobile devices
- **Auto-refresh**: Updates every 2 seconds without page reload
- **NCM Visibility**: Optional power indicator message in asset ID field in NCM devices grid
- **Signal Stats**: Optional modem signal statistics (DBM, SINR, RSRP, RSRQ) in asset ID
- **Voltage Alerts**: Automatic alerts when voltage crosses thresholds
- **Router Model Support**: Automatic detection and model-specific API path handling

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

## Router Model Support

The application automatically detects the router model and uses the appropriate API paths:

### Supported Models

**R980, S400:**
- Watts: `status/power_usage/total`
- Voltage: `status/power_usage/voltage`
- Amperage: `status/power_usage/current`

**R920, R1900, S700, IBR1700, IBR600C, E3000:**
- Watts: `status/power_usage/total`
- Voltage: `status/system/adc/channel/1/voltage` (ADC channel automatically enabled for R920/R1900)
- Amperage: `status/power_usage/current` (if available)

**IBR900:**
- Not supported - application will exit gracefully if detected

For unknown models, the application will attempt to use default paths and log warnings.

## Configuration

### Appdata Fields

**Core Configuration:**
- `power_dashboard_interval`: Polling interval in seconds. Default: 300 (5 minutes)
- `power_dashboard_port`: Web server port. Default: 8000

**Voltage Indicator "Lights" in Asset ID:**

Use these appdata keys to configure voltage indicator message (🟢 12.17V | 0.44A | 5.34W):

- `power_dashboard_lights`: If present (even empty), enables writing a voltage indicator message
- `power_dashboard_lights_path`: Config path to write the message. Default: `config/system/asset_id`
- `power_dashboard_high`: High voltage threshold (V). Default: 12.1
- `power_dashboard_med`: Medium voltage threshold (V). Default: 11.5 (below is low)

**Note**: Lights and signal updates use the same interval as power monitoring (`power_dashboard_interval`). They update once at startup, then follow the configured interval.

Indicator in message: High `🟢`, Medium `🟡`, Low `🔴`, No data (None/0V) `⚫`.

**Signal Statistics in Asset ID:**

- `power_dashboard_signal`: If present (even empty), appends modem signal statistics to the power indicator message
  - Only works when `power_dashboard_lights` is also enabled
  - Uses the same interval as power monitoring (`power_dashboard_interval`)
  - Signal stats format: `DBM: -85dBm | SINR: 15dB | RSRP: -95dBm | RSRQ: -10dB`

Example combined message (lights + signal): `🟢 12.17V | 0.44A | 5.34W | DBM: -85dBm | SINR: 15dB | RSRP: -95dBm | RSRQ: -10dB`

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

### Web Interface Features

**Time Range Selection:**
- **Live**: Real-time monitoring with 1-second polling (data not saved to files)
- **Hour**: Last hour of historical data
- **Day**: Last 24 hours of historical data (default)
- **Week**: Last 7 days of historical data
- **Month**: Last 30 days of historical data

**Note**: The background monitoring thread continues collecting and saving data at the configured interval regardless of which time range is selected in the web interface. This ensures all historical data is available when switching between time ranges.

### Data Retention

- **In-Memory**: Last 24 hours of data for fast web interface access
- **On-Disk**: 30 days of historical data
- **Automatic Calculation**: Data points calculated based on polling interval
  - 5-minute intervals: 8,640 points for 30 days
  - 1-minute intervals: 43,200 points for 30 days
  - 10-minute intervals: 4,320 points for 30 days

**Live Mode**: Live mode data is displayed in real-time but is not saved to files. The regular monitoring thread continues collecting data in the background, so switching back to historical views will show all collected data.

