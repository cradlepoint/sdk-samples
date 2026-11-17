# Motorola SmartConnect
Integrates with Motorola SmartConnect by broadcasting WAN and VPN status as UDP beacons on configured LANs. A web UI provides configuration.

## What It Does

- At the configured interval, sends a UDP packet with a JSON payload to the broadcast address of each enabled LAN
- Payload includes WAN connection status, VPN state, GPS fix (when available), and modem info
- Web UI for configuration, on the port shown in the app log and saved in **Motorola_web_port**

## Accessing the App

Open **http://&lt;router-ip&gt;:&lt;port&gt;/** in a browser. The port is shown in the app log at startup and saved in the **Motorola_web_port** appdata field (usually 8000, or the next free port if 8000 is taken). The log shows it, for example `Bound port 8001 (discovered, saved to Motorola_web_port)` then `Web server started on port 8001`.

To use a specific port on one router or a group, set **Motorola_web_port** in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection. If the configured port is not a number from 1 to 65535, or is still busy after about 10 seconds, the app stops itself and logs why. Fix or delete the field, then start the app.

![image](https://github.com/user-attachments/assets/4e374d86-4119-4d21-b4f0-66a98e11c902)

## Appdata (Configuration)

Set these in the router UI under **System > SDK Data** (or in NCM under the device's SDK app configuration):

| Field | Required | Purpose |
|-------|----------|---------|
| **Motorola_web_port** | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 and saves it here. Delete it to pick a port automatically again. |
| **Motorola_port** | No | Deprecated. Older name for the web port, used only when **Motorola_web_port** is not set. |

Beacon settings (interval, UDP port, networks) are configured through the web UI and stored in appdata automatically.

## Default Configuration

| Setting | Default |
|---------|---------|
| Interval | 5 seconds |
| UDP Port | 21010 |
| Networks | First LAN enabled |

## More Information

[Motorola SmartConnect Homepage](https://www.motorolasolutions.com/en_us/products/p25-products/apx-mission-critical-applications/smartconnect.html)
