# Motorola SmartConnect

Integrates with Motorola SmartConnect by broadcasting WAN and VPN status as UDP beacons on configured LANs. A web UI provides configuration.

## What It Does

- At the configured interval, sends a UDP packet with a JSON payload to the broadcast address of each enabled LAN
- Payload includes WAN connection status, VPN state, GPS fix (when available), and modem info
- Web UI on port 8000 (configurable) for configuration

## Accessing the App

Open **http://&lt;router-ip&gt;:&lt;port&gt;/** in a browser. Default port is 8000. Use the **Motorola_port** appdata field to override.

<img width="815" height="692" alt="image" src="https://github.com/user-attachments/assets/4e374d86-4119-4d21-b4f0-66a98e11c902" />

## Appdata (Configuration)

Set these in the router UI under **System > SDK Data** (or in NCM under the device's SDK app configuration):

| Field | Purpose |
|-------|---------|
| **Motorola_port** | Web UI port. Default: 8000. |

Beacon settings (interval, UDP port, networks) are configured through the web UI and stored in appdata automatically.

## Default Configuration

| Setting | Default |
|---------|---------|
| Interval | 5 seconds |
| UDP Port | 21010 |
| Networks | First LAN enabled |

## More Information

[Motorola SmartConnect Homepage](https://www.motorolasolutions.com/en_us/products/p25-products/apx-mission-critical-applications/smartconnect.html)
