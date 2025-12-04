# Installer_UI

Installer_UI provides a simple web interface for installers to configure WiFi settings and run speedtests on the router.

[Download the built app from our releases page!](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)

![image](https://github.com/user-attachments/assets/a0af6ae2-a9dd-46de-a294-10c8468cec8d)

![image](https://github.com/user-attachments/assets/a91d5828-e81e-47a1-a16b-e8c1240240d1)

![image](https://github.com/user-attachments/assets/2a74cdae-491c-42d6-9502-7436e3058d97)

## Access

The web interface is available on port 8000. Access it by:
- Connecting to WiFi or LAN port and browsing to `http://192.168.0.1:8000` or `cp:8000/`
- The application automatically configures firewall forwarding from Primary LAN Zone to Router Zone

## Features

- **WiFi Configuration**: View current SSID and configure WiFi SSID and password
- **Speedtest**: Run Ookla speedtests to measure download/upload speeds
- **Signal Monitor**: View signal quality metrics (RSSI, SINR, RSRP, RSRQ)
- **QR Code**: Generate QR codes for WiFi network credentials

## SDK Appdata Configuration

Configure these settings in System > SDK Data:

- **installer_password** - Password required to make changes. Defaults to device serial number if not set.

## Usage

All configuration changes require entering the installer password. The password defaults to the device serial number and can be changed in System > SDK Data.
