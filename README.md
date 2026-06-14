# Ericsson Cradlepoint NCOS SDK

**Extend your Ericsson routers with custom Python applications.**

The NCOS SDK enables developers to build and deploy Python applications that run directly on Ericsson Cradlepoint NetCloud OS (NCOS) routers. Create custom logic for connectivity management, IoT data collection, monitoring, automation, and more—without replacing hardware.

---

## App Store

Browse, search, and download ready-to-use sample applications:

**[Open the App Store](https://cradlepoint.github.io/sdk-samples/)**

---

## Why Custom Applications on Ericsson Routers?

- **Extend without hardware changes** — Add new capabilities through software while your existing Ericsson/Cradlepoint fleet stays in place.
- **Access router internals** — Query modem signal strength, WAN status, GPS, connected clients, and system metrics via a Python API.
- **Integrate with your stack** — Push data to cloud platforms (Azure IoT, Splunk, MQTT), trigger alerts, or automate workflows based on router state.
- **Deploy at scale** — Build once, distribute via NetCloud Manager to thousands of devices with group-based assignment.
- **Standard Python** — Use familiar libraries and patterns; the SDK provides a simple `cp` module for router interaction.

---

## Resources

| Resource | Link |
|----------|------|
| **App Store** | [Browse & download apps](https://cradlepoint.github.io/sdk-samples/) |
| **SDK Developer Guide** | [docs/NCOS_SDK_Developer_Guide.md](docs/NCOS_SDK_Developer_Guide.md) |
| **NCOS SDK Developers Guide** | [Documentation](https://docs.cradlepoint.com/r/NCOS-SDK-Developers_Guide) |
| **NetCloud Manager — SDK apps** | [Tools Tab](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab) |

---

## Repository Structure

```
├── apps/                   # Sample applications organized by category
│   ├── connectivity/       # Speed tests, WAN management, failover
│   ├── monitoring/         # System metrics, signal, power, clients
│   ├── networking/         # QoS, VPN, MAC filtering, hotspot
│   ├── integrations/       # MQTT, Splunk, FTP, IFTTT
│   ├── gpio/              # GPIO, USB, hardware control
│   ├── vehicle/           # GPS, OBD-II, geofencing, speed limits
│   ├── security/          # Encryption, IP Verify
│   ├── web_tools/         # Dashboards, packet capture, CS explorer
│   ├── examples/          # Hello world, shell, ping
│   ├── templates/         # app_template, web_app_template
│   └── archive/           # Retired/inactive apps
├── docs/                  # API documentation and app store site
├── make.py                # Build/deploy tool
└── sdk_settings.ini       # Router connection settings
```

---

## Development Environment Setup

### 1. Install Python

Install Python 3.8 or later from [python.org](https://www.python.org/downloads/).

### 2. Clone and set up

```bash
git clone https://github.com/cradlepoint/sdk-samples.git
cd sdk-samples
```

#### Windows

```cmd
python make.py setup
```

#### macOS / Linux

```bash
python3 make.py setup
```

This creates a `.venv` virtual environment and installs all Python dependencies.

### 3. Configure router connection

Edit `sdk_settings.ini` with your dev router's IP and credentials:

```ini
[sdk]
app_name=hello_world
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password
```

---

## Quick Start — make.py

```bash
# Create a new app
python3 make.py create my_app

# Build a single app (searches apps/ recursively)
python3 make.py build my_app

# Build all apps
python3 make.py build all

# Deploy to connected router (purge + build + install + start)
python3 make.py deploy my_app

# Check status
python3 make.py status my_app
```

| Action | Description |
|--------|-------------|
| **create** | Scaffold a new app from `app_template` |
| **build** | Package an app as `.tar.gz` for deployment |
| **deploy** | Full lifecycle: purge → build → install → verify |
| **status** | Show app state on the connected router |
| **start / stop** | Control a running app |
| **uninstall** | Remove app from router |
| **clean** | Remove local build artifacts |

---

## License

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service ("TSLA").

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER'S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED "AS-IS," WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER'S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER'S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc. All rights reserved.
