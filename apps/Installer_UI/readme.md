# Installer_UI
Installer_UI provides a simple web interface for installers to configure WiFi settings and run speedtests on the router.

![image](https://github.com/user-attachments/assets/a0af6ae2-a9dd-46de-a294-10c8468cec8d)

![image](https://github.com/user-attachments/assets/a91d5828-e81e-47a1-a16b-e8c1240240d1)

![image](https://github.com/user-attachments/assets/2a74cdae-491c-42d6-9502-7436e3058d97)

## Access

The web interface port is shown in the app log at startup and saved in the `Installer_UI_web_port` SDK Data field (usually 8000, or the next free port if 8000 is taken). Access it by:
- Connecting to WiFi or LAN port and browsing to `http://<router_ip>:<port>` (for example `http://192.168.0.1:<port>` or `cp:<port>/`)
- The application automatically configures firewall forwarding from Primary LAN Zone to Router Zone

The startup log shows the port, for example `Bound port 8000 (discovered, saved to Installer_UI_web_port)` followed by `Web server started on port 8000`. To use a specific port on one router or a group, set `Installer_UI_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection. If the configured port is not a number from 1 to 65535, or is still busy after about 10 seconds, the app stops itself and logs why. Fix or delete the field, then start the app.

## Features

- **WiFi Configuration**: View current SSID and configure WiFi SSID and password
- **Speedtest**: Run Ookla speedtests to measure download/upload speeds
- **Signal Monitor**: View signal quality metrics (RSSI, SINR, RSRP, RSRQ)
- **QR Code**: Generate QR codes for WiFi network credentials

## Appdata Fields

Configure these settings in System > SDK Data, or in NCM SDK Data for a device or group:

| Field | Required | Description |
|-------|----------|-------------|
| `installer_password` | No | Password required to make changes. Defaults to the device serial number if not set. |
| `Installer_UI_web_port` | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 and saves it here. Delete it to pick a port automatically again. |

## Usage

All configuration changes require entering the installer password. The password defaults to the device serial number and can be changed in System > SDK Data.
