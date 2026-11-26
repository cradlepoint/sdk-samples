# Installer_UI
Installer_UI provides a simple web interface for installers to configure WiFi settings and run speedtests on the router.

<img width="400" height="867" alt="image" src="https://github.com/user-attachments/assets/b06ef028-2851-44e9-84d1-d08238f89e23" />
<img width="400" height="867" alt="image" src="https://github.com/user-attachments/assets/586d15cb-cf9a-4485-87d4-c18445ad89ab" />

## Access

The web interface port is shown in the app log at startup and saved in the `Installer_UI_web_port` SDK Data field (usually 8000, or the next free port if 8000 is taken). Access it by:
- Connecting to WiFi or LAN port and browsing to `http://<router_ip>:<port>` (for example `http://192.168.0.1:<port>` or `cp:<port>/`)
- The application automatically configures firewall forwarding from Primary LAN Zone to Router Zone

The startup log shows the port, for example `Bound port 8000 (discovered, saved to Installer_UI_web_port)` followed by `Web server started on port 8000`. To use a specific port on one router or a group, set `Installer_UI_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection. If the configured port is not a number from 1024 to 65535, or is still busy after about 10 seconds, the app stops itself and logs why. Fix or delete the field, then start the app.

## Features

- **WiFi Configuration**: View current SSID and configure WiFi SSID and password
- **Speedtest**: Run Ookla speedtests to measure download/upload speeds
- **Signal Monitor**: View signal quality metrics (RSSI, SINR, RSRP, RSRQ)

## Appdata Fields

Configure these settings in System > SDK Data, or in NCM SDK Data for a device or group:

| Field | Required | Description |
|-------|----------|-------------|
| `installer_password` | No | Password required to make changes. Defaults to the device serial number if not set. |
| `Installer_UI_web_port` | No | Web UI port (1024-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 (up to 8100) and saves it here. Delete it to pick a port automatically again. |

## Usage

All configuration changes require entering the installer password. The password defaults to the device serial number and can be changed in System > SDK Data.
