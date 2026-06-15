# Ericsson NCOS SDK — Complete Developer Manual

A comprehensive reference for building, deploying, and managing Python applications on Ericsson Cradlepoint routers running NetCloud OS (NCOS).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Environment Setup](#2-environment-setup)
3. [Project Structure](#3-project-structure)
4. [The cp Module — Full API Reference](#4-the-cp-module--full-api-reference)
5. [Build Tool (make.py)](#5-build-tool-makepy)
6. [Application Configuration](#6-application-configuration)
7. [Router Environment Constraints](#7-router-environment-constraints)
8. [Web Applications](#8-web-applications)
9. [Working with Third-Party Libraries](#9-working-with-third-party-libraries)
10. [Event Registration and Callbacks](#10-event-registration-and-callbacks)
11. [Application Data (Appdata)](#11-application-data-appdata)
12. [GPS and Location](#12-gps-and-location)
13. [Speed Testing](#13-speed-testing)
14. [GPIO](#14-gpio)
15. [CLI Access (csterm) and Web Terminal (ttyd)](#15-cli-access-csterm-and-web-terminal-ttyd)
16. [Containers on NCOS](#16-containers-on-ncos)
17. [Local Development](#17-local-development)
18. [Production Deployment via NCM](#18-production-deployment-via-ncm)
19. [Debugging and Troubleshooting](#19-debugging-and-troubleshooting)
20. [Complete Examples](#20-complete-examples)

---

## 1. Overview

The NCOS SDK enables Python applications to run directly on Ericsson Cradlepoint routers. Applications execute on the device itself, providing programmatic access to modem diagnostics, WAN status, GPS, LAN clients, GPIO, serial ports, and the full NCOS configuration and status tree.

### What You Can Build

- Signal monitoring and alerting
- Custom web dashboards
- Cloud integrations (MQTT, Splunk, Azure IoT)
- Automated site surveys
- GPS tracking and geofencing
- OBD-II vehicle telemetry
- Bandwidth management and QoS automation
- Hotspot splash pages and captive portals
- IoT device integration via serial/USB

### Architecture

```
┌─────────────────────────────────────────────┐
│              Your Application                │
│         (Python 3.8, pure .py files)        │
├─────────────────────────────────────────────┤
│               cp.py Module                  │
│    (communicates via Unix socket on router   │
│     or HTTP REST when running locally)       │
├─────────────────────────────────────────────┤
│         NCOS Config Store (cs.sock)         │
│     status/  config/  control/  state/      │
├─────────────────────────────────────────────┤
│            NCOS Router Hardware              │
│   Modems │ GPS │ WiFi │ GPIO │ Ethernet     │
└─────────────────────────────────────────────┘
```

---

## 2. Environment Setup

### Prerequisites

- Python 3.8 or later on your development machine
- Git
- An Ericsson Cradlepoint router with Developer Mode enabled (via NetCloud Manager)

### Clone and Install

```bash
git clone https://github.com/cradlepoint/sdk-samples.git
cd sdk-samples
```

**Windows:**
```cmd
python make.py setup
```

**macOS / Linux:**
```bash
python3 make.py setup
```

This creates a `.venv` virtual environment and installs all dependencies from `requirements.txt` (requests, cryptography, paramiko, pyserial).

### Configure Router Connection

Edit `sdk_settings.ini` in the repository root:

```ini
[sdk]
app_name=hello_world
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password
```

| Field | Description |
|-------|-------------|
| `app_name` | Default app name for commands when not specified |
| `dev_client_ip` | Router IP address on your network |
| `dev_client_username` | Router admin username |
| `dev_client_password` | Router admin password |

### Enable Developer Mode

Developer Mode must be enabled in **NetCloud Manager** (not the router's local UI):

1. Log in to NetCloud Manager
2. Navigate to the device
3. Enable SDK Developer Mode under device settings

---

## 3. Project Structure

### Repository Layout

```
sdk-samples/
├── apps/                       # All sample applications
│   ├── hello_world/            # Minimal example
│   ├── mqtt_app/               # MQTT integration
│   ├── speedtest_web/          # Web-based speed test
│   ├── ...                     # 75+ apps
│   ├── templates/              # Scaffolding templates
│   │   ├── app_template/       # Basic app template
│   │   └── web_app_template/   # Web app with UI
│   └── archive/                # Retired apps
├── docs/                       # Documentation
├── make.py                     # Build/deploy tool
├── sdk_settings.ini            # Router connection settings
└── requirements.txt            # Python dependencies
```

### Application Layout

Every SDK application follows this structure:

```
my_app/
├── package.ini          # Application metadata (UUID, version, vendor)
├── start.sh             # Entry point — must use cppython
├── cp.py                # SDK communication library (auto-generated)
├── my_app.py            # Your application logic
├── readme.md            # Documentation and appdata fields
└── METADATA/            # Auto-generated during build (signatures)
    ├── MANIFEST.json
    └── SIGNATURE.DS
```

### package.ini

```ini
[my_app]
uuid = a58c82ba-cb00-4219-a98f-5305aa13efd7
vendor = Ericsson
notes = Description of your app
version_major = 1
version_minor = 0
version_patch = 0
auto_start = true
restart = true
reboot = true
firmware_major = 7
firmware_minor = 26
developer = Ericsson
tags = monitoring, web
```

| Field | Description |
|-------|-------------|
| `uuid` | Unique identifier (auto-generated on first build) |
| `vendor` | Your organization name |
| `notes` | Brief description |
| `version_major/minor/patch` | Semantic version |
| `auto_start` | Start automatically after install |
| `restart` | Restart on crash |
| `reboot` | Survive router reboots |
| `firmware_major/minor` | Minimum NCOS firmware required |
| `tags` | Comma-separated categories for discovery |

### start.sh

```bash
#!/bin/bash
cppython my_app.py
```

Always use `cppython` — never `python` or `python3`. The router's Python interpreter is `cppython`.

---

## 4. The cp Module — Full API Reference

Import at the top of every application:

```python
import cp
```

The `cp` module communicates with the router's config store via Unix socket (on-router) or HTTP REST (local development). All functions are module-level — no classes to instantiate.

### 4.1 Logging and Alerts

```python
cp.log(value: str)
```
Log a message to syslog (router), stdout (container), or console (local). **Always use this instead of `print()`.**

```python
cp.alert(value: str) -> Optional[Dict]
```
Send a custom alert to NetCloud Manager. Only works on-router.

### 4.2 CRUD Operations

These are the core functions for reading and writing to the router's data tree.

```python
cp.get(base: str, query: str = '', tree: int = 0) -> Any
```
Read data from the status/config tree. Returns the data directly (not wrapped).

```python
cp.put(base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict]
```
Update data in the config/control/state tree.

```python
cp.post(base: str, value: Any = '', query: str = '') -> Optional[Dict]
```
Create new entries in the config tree.

```python
cp.delete(base: str, query: str = '') -> Optional[Dict]
```
Delete entries from the config tree.

```python
cp.patch(value: List) -> Optional[Dict]
```
Bulk add/remove from the config tree. Value format: `[adds_dict, removals_list]`.

```python
cp.decrypt(base: str, query: str = '', tree: int = 0) -> Any
```
Decrypt and retrieve encrypted data (e.g., certificate private keys). Only works on-router.

**Examples:**

```python
# Read system uptime
uptime = cp.get('status/system/uptime')

# Read WAN connection state
state = cp.get('status/wan/connection_state')

# Write a config value
cp.put('config/system/asset_id', 'Site-42-Router')

# Trigger a reboot
cp.put('control/system/reboot', 'reboot hypmgr')

# Create a new user
cp.post('config/system/users/', {"username": "sdk", "password": "pass", "group": "admin"})
```

### 4.3 Device Information

```python
cp.get_name() -> Optional[str]                          # Device name (system_id)
cp.get_mac(format_with_colons=False) -> Optional[str]   # MAC address
cp.get_serial_number() -> Optional[str]                 # Serial number
cp.get_product_type() -> Optional[str]                  # Product name (e.g. 'IBR900-600M')
cp.get_router_model() -> Optional[str]                  # Model only (e.g. 'IBR900')
cp.get_firmware_version(include_build_info=False) -> str # Firmware version string
cp.get_uptime() -> int                                  # Uptime in seconds
cp.get_temperature(unit='fahrenheit') -> Optional[float]# Device temperature
cp.get_description() -> Optional[str]                   # Device description
cp.get_asset_id() -> Optional[str]                      # Asset ID
```

### 4.4 Wait Helpers

```python
cp.wait_for_wan_connection(timeout=300) -> bool   # Wait for WAN to connect
cp.wait_for_uptime(min_uptime_seconds=60) -> None # Wait for minimum uptime
cp.wait_for_ntp(timeout=300) -> bool              # Wait for NTP sync
```

### 4.5 GPS and Location

```python
cp.get_lat_long(max_retries=5) -> Tuple[Optional[float], Optional[float]]
cp.get_gps_status() -> Dict[str, Any]  # lock, satellites, lat, lon, altitude, speed, heading
cp.dec(deg, minutes=0.0, sec=0.0) -> Optional[float]  # DMS to decimal degrees
```

### 4.6 WAN and Connectivity

```python
cp.get_wan_connection_state() -> Optional[str]     # 'connected', 'disconnected', etc.
cp.get_wan_ip_address() -> Optional[str]           # WAN IP
cp.get_wan_primary_device() -> Optional[str]       # Primary WAN device UID
cp.get_connected_wans(max_retries=10) -> List[str] # Connected WAN device UIDs
cp.get_sims(max_retries=10) -> List[str]           # Modem UIDs with SIMs installed
cp.get_wan_status() -> Optional[Dict]              # Full WAN status with all devices
cp.get_wan_devices() -> Optional[Dict]             # Device list with basic status
cp.get_wan_devices_status() -> Optional[Dict]      # Raw WAN devices status tree
cp.get_wan_device_summary() -> Optional[Dict]      # Summary with profile info
```

### 4.7 Signal Strength and Modem Diagnostics

```python
cp.get_signal_strength(uid=None, include_backlog=False) -> Optional[Dict]
cp.get_wan_modem_diagnostics(device_id: str) -> Optional[Dict]
cp.get_wan_modem_stats(device_id: str) -> Optional[Dict]
cp.get_wan_ethernet_info(device_id: str) -> Optional[Dict]
```

Signal strength returns: `signal_strength`, `rsrp`, `rsrp_5g`, `rsrq`, `rsrq_5g`, `sinr`, `sinr_5g`, `dbm`, `rf_band`, `service_type`, `cellular_health_score`, `cellular_health_category`, and more.

### 4.8 LAN and Clients

```python
cp.get_lan_clients() -> Dict                        # IPv4/IPv6 client counts and lists
cp.get_ipv4_wired_clients() -> List[Dict]           # Wired clients with hostname resolution
cp.get_ipv4_wifi_clients() -> List[Dict]            # WiFi clients with SSID, signal, band
cp.get_ipv4_lan_clients() -> Dict                   # Combined wired + WiFi
cp.get_lan_status() -> Optional[Dict]               # Full LAN status
cp.get_lan_networks() -> Optional[Dict]             # LAN network info
cp.get_lan_devices() -> Optional[Dict]              # LAN device info
cp.get_lan_statistics() -> Optional[Dict]           # LAN traffic stats
```

### 4.9 WLAN (WiFi)

```python
cp.get_wlan_status() -> Optional[Dict]              # Full WLAN status
cp.get_wlan_clients() -> List[Dict]                 # Connected wireless clients
cp.get_wlan_radio_status() -> List[Dict]            # Radio status for all bands
cp.get_wlan_radio_by_band(band='2.4 GHz') -> Optional[Dict]
cp.get_wlan_state() -> str                          # 'On', 'Off', etc.
cp.get_wlan_events() -> Dict                        # WLAN events
cp.get_wlan_channel_info(band=None) -> Dict         # Channel info
cp.get_wlan_client_count() -> int                   # Total WiFi clients
cp.get_wlan_client_count_by_band() -> Dict[str, int]
```

### 4.10 System Status

```python
cp.get_system_status() -> Optional[Dict]  # uptime, cpu, memory, disk, services
cp.get_comprehensive_status() -> Optional[Dict]  # Everything in one call
```

System status returns: `uptime`, `temperature`, `cpu_usage`, `memory` (total/used/free/percentage), `disk` (total/used/free/percentage), `services_running`, `services_disabled`.

### 4.11 Network Services

```python
cp.get_dhcp_status() -> Optional[Dict]      # DHCP status with leases
cp.get_dhcp_leases() -> Optional[List]      # Lease list
cp.get_dns_status() -> Optional[Dict]       # DNS cache stats
cp.get_firewall_status() -> Optional[Dict]  # Connection tracking, hit counters
cp.get_openvpn_status() -> Optional[Dict]   # OpenVPN tunnel status
cp.get_vpn_status() -> Optional[Dict]       # Combined VPN (OpenVPN, L2TP, GRE, VXLAN)
cp.get_hotspot_status() -> Optional[Dict]   # Hotspot clients/sessions
cp.get_qos_status() -> Optional[Dict]       # QoS queues and packets
cp.get_routing_table() -> Optional[Dict]    # Routing information
cp.get_services_status() -> Optional[Dict]  # System services
cp.get_apps_status() -> Optional[Dict]      # Internal + SDK apps
cp.get_sdwan_status() -> Optional[Dict]     # SD-WAN advanced status
cp.get_flow_statistics() -> Optional[Dict]  # Flow stats with destinations
cp.get_client_usage() -> Optional[Dict]     # Per-client bandwidth stats
cp.get_power_usage() -> Optional[Dict]      # Power consumption
cp.get_storage_status() -> Optional[Dict]   # Storage health
cp.get_sensors_status() -> Optional[Dict]   # Level/day sensors
cp.get_iot_status() -> Optional[Dict]       # IoT status
cp.get_event_status() -> Optional[Dict]     # System events
cp.get_obd_status() -> Optional[Dict]       # OBD vehicle diagnostics
cp.get_certificate_status() -> Optional[Dict]
cp.get_security_status() -> Optional[Dict]  # Firewall + security + certs
```

### 4.12 NCM (NetCloud Manager)

```python
cp.get_ncm_status() -> Optional[str]        # 'connected', 'disconnected'
cp.get_ncm_router_id() -> Optional[str]     # NCM client ID
cp.get_ncm_group_name() -> Optional[str]    # NCM group name
cp.get_ncm_account_name() -> Optional[str]  # NCM account name
cp.get_ncm_api_keys() -> Optional[Dict]     # API keys from cert management
```

### 4.13 Diagnostics

```python
cp.ping_host(host, count=4, packet_size=56) -> Optional[Dict]
# Returns: host, num, size, tx, rx, loss, min, avg, max

cp.traceroute_host(host, max_hops=30) -> Optional[Dict]
# Returns: host, hops, hop_count, raw_output

cp.execute_cli(commands, timeout=10, clean=True) -> Optional[str]
# Execute CLI commands and return output

cp.dns_lookup(hostname, record_type="A") -> Optional[Dict]
cp.clear_dns_cache() -> Optional[Dict]
cp.stop_ping() -> Optional[Dict]
```

### 4.14 Speed Test (Netperf)

```python
cp.speed_test(host="", interface="", duration=5, packet_size=0,
              protocol="tcp", direction="both") -> Optional[Dict]
# Returns: download_bps, upload_bps, latency_ms, test_duration, interface, host, protocol

cp.stop_speed_test() -> Optional[Dict]
```

### 4.15 WAN Profile Management

```python
cp.get_wan_profiles() -> Optional[List[Dict]]           # All profiles sorted by priority
cp.get_wan_device_profile(device_id) -> Optional[Dict]  # Profile for specific device
cp.set_wan_device_priority(device_id, priority) -> bool # Set priority
cp.enable_wan_device(device_id) -> bool                 # Enable device
cp.disable_wan_device(device_id) -> bool                # Disable device
cp.make_wan_device_highest_priority(device_id) -> bool  # Make highest priority
cp.set_wan_device_default_connection_state(device_id, state) -> bool
cp.set_wan_device_bandwidth(device_id, ingress_kbps=None, egress_kbps=None) -> bool
cp.set_manual_apn(device_or_id, new_apn) -> Optional[Dict]
cp.remove_manual_apn(device_or_id) -> Optional[Dict]
cp.add_advanced_apn(carrier, apn) -> Optional[Dict]
cp.delete_advanced_apn(carrier_or_apn) -> Optional[Dict]
```

### 4.16 User Management

```python
cp.create_user(username, password, group="admin") -> Dict
cp.get_users() -> Dict
cp.delete_user(username) -> Dict
cp.ensure_user_exists(username, password, group="admin") -> Dict
cp.ensure_fresh_user(username, group="admin") -> Dict  # Delete + recreate with random password
cp.validate_password(username, password) -> Dict       # On-router only
```

### 4.17 Device Management

```python
cp.reboot_device() -> None
cp.set_description(description) -> Optional[Dict]
cp.set_asset_id(asset_id) -> Optional[Dict]
cp.set_name(name) -> Optional[Dict]
```

### 4.18 GPIO

```python
cp.get_gpio(gpio_name=None, router_model=None) -> Any
cp.get_all_gpios() -> Dict[str, Any]
cp.get_available_gpios(router_model=None) -> List[str]
```

Supported models and GPIO names:

| Model | Available GPIOs |
|-------|----------------|
| IBR200 | power_input, power_output |
| IBR600 | power_input, power_output |
| IBR900 | power_input, power_output, sata_1–4, sata_ignition_sense |
| IBR1100 | power_input, power_output, expander_1–3 |
| R920 | power_input, power_output |
| R980 | power_input, power_output |
| R1900 | power_input, power_output, expander_1–3, accessory_1 |

### 4.19 Certificates

```python
cp.extract_cert_and_key(cert_name_or_uuid) -> Tuple[Optional[str], Optional[str]]
# Returns: (cert_filename, key_filename) as .pem files
```

### 4.20 Log Monitoring and SMS

```python
cp.monitor_log(pattern=None, callback=None, follow=True, max_lines=0, timeout=0) -> Optional[Dict]
cp.stop_monitor_log(monitor_result) -> Dict
cp.monitor_sms(callback, timeout=0) -> Optional[Dict]
cp.stop_monitor_sms(monitor_result) -> Dict
cp.send_sms(phone_number, message, port=None) -> Optional[str]
```

### 4.21 Packet Capture

```python
cp.start_packet_capture(interface="any", filter_expr="", count=20,
                        timeout=600, url="", filename="") -> Optional[Dict]
cp.stop_packet_capture() -> Dict
cp.download_packet_capture(filename, local_path=None, capture_params=None) -> Optional[Dict]
```

### 4.22 File Server

```python
cp.start_file_server(folder_path="files", port=8000, host="0.0.0.0",
                     title="File Download") -> Optional[Dict]
```
Starts a web file server with a responsive UI for downloading files.

### 4.23 Event Registration

```python
cp.register(action='put', path='', callback=None, *args) -> Optional[Dict]
cp.unregister(eid) -> Optional[Dict]
```

See [Section 10](#10-event-registration-and-callbacks) for full details.

### 4.24 Appdata

```python
cp.get_appdata(name='') -> Union[Optional[str], Optional[List[Dict]]]
cp.put_appdata(name, value) -> None
cp.post_appdata(name, value) -> None
cp.delete_appdata(name) -> None
```

See [Section 11](#11-application-data-appdata) for full details.

---

## 5. Build Tool (make.py)

All commands use the virtual environment Python:

**macOS / Linux:**
```bash
.venv/bin/python make.py <command> [app_name]
```

**Windows:**
```cmd
.venv\Scripts\python make.py <command> [app_name]
```

### Command Reference

| Command | Description |
|---------|-------------|
| `create <name>` | Scaffold a new app from template |
| `build <name>` | Package app as `.tar.gz` |
| `build all` | Build all apps |
| `deploy <name>` | Full lifecycle: purge → build → install → show logs |
| `install <name>` | Transfer package to router via SSH |
| `start <name>` | Start app on router |
| `stop <name>` | Stop app on router |
| `status` | Show SDK status on router |
| `uninstall <name>` | Remove app from router |
| `purge` | Remove ALL apps from router |
| `clean <name>` | Remove local build artifacts |
| `clean all` | Clean all apps |
| `setup` | Create .venv and install dependencies |
| `uuid` | Generate UUID for app |
| `update` | Check for SDK updates from GitHub |

### Creating a New App

```bash
.venv/bin/python make.py create my_new_app
```

This copies `apps/templates/app_template/` to `./my_new_app/` at the repo root, renames the main file, and updates all internal references. Edit `my_new_app.py` and `readme.md`. When ready, move to apps:

```bash
mv my_new_app apps/
```

### Deploying

```bash
.venv/bin/python make.py deploy my_app
```

This runs the full deployment cycle:
1. **Purge** — Remove all apps from router
2. **Build** — Package as versioned `.tar.gz`
3. **Install** — Transfer via SSH (paramiko)
4. **Verify** — Show recent logs to confirm startup

The app auto-starts after install (`auto_start = true`).

### Build Ignore

Exclude files from the package by creating a `buildignore` file in your app directory:

```
# Development files
test_data.json
requirements.txt
tests/
docs/
```

Always excluded automatically: `__pycache__/`, `buildignore`, `.DS_Store`.

---

## 6. Application Configuration

### sdk_settings.ini

The build tool reads router connection details from `sdk_settings.ini`:

```ini
[sdk]
app_name=my_app
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password
```

The `app_name` field is the default when no app name is passed to make.py commands.

### package.ini Tags

Tags categorize apps for the App Store and discovery:

`connectivity`, `monitoring`, `networking`, `integrations`, `gpio`, `vehicle`, `security`, `web`, `tools`, `examples`, `speedtest`, `mqtt`

---

## 7. Router Environment Constraints

### Python 3.8

The router runs `cppython` (Python 3.8). Key restrictions:

```python
# ❌ WRONG — union type syntax (Python 3.10+)
value: str | None = None

# ✅ CORRECT — use Optional
from typing import Optional
value: Optional[str] = None
```

### No Screen, No Keyboard

```python
# ❌ WRONG
print("Hello")          # Use cp.log() instead
input("Enter value:")   # No keyboard exists

# ✅ CORRECT
cp.log("Hello")
value = cp.get_appdata('my_setting')
```

### File System Rules

- **Relative paths only** — use `tmp/`, never `/tmp/`
- **Create directories first** — `os.makedirs('tmp', exist_ok=True)`
- **NEVER modify packaged files** — router deletes the app if any file from the original package is modified. Write to new files only
- **No .pyc or .so files** — only pure Python (.py) is supported

### Available Standard Library Modules

`threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`, `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`, `time`, `xml.etree.ElementTree`

### Missing Standard Library Modules

`pkg_resources`, `decimal`, `csv` — copy shims from `apps/5GSpeed/` or `apps/Mobile_Site_Survey/` if needed.

### Pre-installed System Libraries

`requests` is available system-wide on `cppython`. Do NOT bundle it in your app folder.

### Architecture

ARM64 (aarch64) with musl libc. When downloading binaries, always use `aarch64`/`arm64` variants.

---

## 8. Web Applications

### Basic Pattern

```python
import cp
import json
import socket
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

PORT = 8000

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            data = cp.get('status/system') or {}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            super().do_GET()

cp.log('Starting web server...')
server = HTTPServer(('', PORT), MyHandler)
server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
Thread(target=server.serve_forever, daemon=True).start()
cp.log(f'Web server started on port {PORT}')

while True:
    time.sleep(60)
```

### Web Development Rules

- **Port 8000** is the default
- **Always set SO_REUSEADDR** before binding
- **Run in a daemon thread** so the main thread handles app logic
- **Serve all assets locally** — no external CDNs
- **Use Python's built-in `http.server`** — never use Flask, Bottle, etc.
- **Vanilla JavaScript** — ES6+ is fine (arrow functions, async/await, template literals)
- **Never pass parameters in onclick attributes** — use data attributes instead

### Web App Template

When creating web apps, copy the template at `apps/templates/web_app_template/`:

```
web_app_template/
├── package.ini
├── start.sh
├── cp.py
├── web_app_template.py      # HTTP server
├── your_web_app.html        # Starting HTML (copy as index.html)
└── static/
    ├── css/style.css        # Complete design system
    ├── js/script.js         # Navigation, dark mode, search
    └── libs/                # jQuery, Font Awesome
```

Copy `your_web_app.html` as `index.html` and the `static/` folder into your app. Modify the title, sidebar nav, and content sections.

### LAN Client Access

For LAN clients to reach your app's web server, the router firewall must have a forwarding rule from the Primary LAN Zone to the Router Zone. Check `config/firewall/zone_fwd` or NCOS UI → Security → Zone Firewall.

---

## 9. Working with Third-Party Libraries

### Installing

Install directly into your app folder:

```bash
# macOS / Linux
.venv/bin/pip install -t apps/my_app/ library_name

# Windows
.venv\Scripts\pip install -t apps\my_app\ library_name
```

### Rules

- Only pure Python (`.py`) files — remove any `.pyc`, `.so`, `.pyd`
- Libraries must be compatible with Python 3.8
- Keep dependencies minimal (app size limit: 60 MB)
- Delete `egg-info` and `dist-info` directories after install
- `requests` is pre-installed on the router — do NOT bundle it
- `redis` is NOT available — make it conditional with try/except

### Common Libraries That Work

- `paho-mqtt` — MQTT client
- `pynmeagps` — NMEA sentence parsing (always install fresh, never copy)
- `pyserial` — Serial port access

### CSV Workaround

The `csv` module's C implementation isn't available on cppython. For simple CSV writing, use string concatenation:

```python
line = ','.join(fields) + '\n'
```

---

## 10. Event Registration and Callbacks

Register callbacks that fire when specific API paths change. **Only works on-router.**

```python
import cp

def on_wan_change(path, value, args):
    cp.log(f'WAN state changed: {value}')

cp.register('put', 'status/wan/connection_state', on_wan_change)
```

### Callback Signature

```python
def my_callback(path: str, value: Any, args: tuple):
    pass
```

- `path` — the config store path that triggered the event
- `value` — the new value at that path
- `args` — a single tuple of any extra arguments passed during registration

### Key Rules

- **Use `'put'` (lowercase) for control tree paths** — `'set'` or `'PUT'` silently fails
- **Do NOT cp.put() to seed the control tree before cp.register()** — causes socket desync
- The callback receives exactly 3 arguments — do NOT use `*args` unpacking
- Control tree keys persist across app redeploys (router merges, never replaces)

### Control Tree Pattern

Use the control tree to receive external triggers:

```python
import cp
import time

def handle_command(path, value, args):
    cp.log(f'Received command: {value}')
    if value == 'refresh':
        # Do something
        pass

cp.register('put', 'control/my_app/command', handle_command)

while True:
    time.sleep(1)
```

---

## 11. Application Data (Appdata)

Appdata provides per-app key-value storage configurable from NetCloud Manager. Use it for user-configurable settings.

### Reading

```python
server_url = cp.get_appdata('server_url')
if not server_url:
    server_url = 'https://default.example.com'  # Code default
    cp.log('No server_url configured, using default')
```

### Writing

```python
cp.put_appdata('last_run', '2025-01-15T10:30:00')
```

### Critical Rules

- **NEVER write default values to appdata** — this overrides NCM group-level configurations
- **Always call with a field name** — `cp.get_appdata('field_name')`
- `cp.get_appdata()` without args returns a LIST of all entries, not a dict
- `cp.put_appdata(name, value)` takes TWO string arguments, not a dict
- Appdata is stored at `config/system/sdk/appdata`
- Document all appdata fields in your `readme.md`

### Pattern

```python
# Good pattern: read with code defaults
interval = cp.get_appdata('poll_interval')
interval = int(interval) if interval else 30  # Default 30s

target = cp.get_appdata('target_host')
if not target:
    target = '8.8.8.8'
    cp.log('No target_host configured, using default')
```

---

## 12. GPS and Location

### Basic Position

```python
lat, lon = cp.get_lat_long()
if lat is not None:
    cp.log(f'Position: {lat}, {lon}')
```

### Full GPS Status

```python
gps = cp.get_gps_status()
# Returns: gps_lock, satellites, latitude, longitude, altitude, speed, heading, accuracy
```

### NMEA Parsing

Use `pynmeagps` for NMEA sentence parsing:

```bash
.venv/bin/pip install -t apps/my_app/ pynmeagps
```

```python
from pynmeagps import NMEAReader
import cp

sentences = cp.get('status/gps/nmea')
if sentences:
    for sentence in sentences:
        try:
            msg = NMEAReader.parse(sentence)
            if msg.msgID == 'GGA':
                cp.log(f'lat={msg.lat} lon={msg.lon} alt={msg.alt}m sats={msg.numSV}')
            elif msg.msgID == 'RMC' and msg.status == 'A':
                speed_kmh = msg.spd * 1.852
                cp.log(f'speed={speed_kmh:.1f} km/h course={msg.cog}°')
        except Exception as e:
            pass  # PCPTMINR (proprietary) raises "Unknown msgID" — expected
```

---

## 13. Speed Testing

### Using cp.speed_test() (Netperf — Built-in)

```python
result = cp.speed_test(interface='rmnet501', duration=10, direction='both')
if result:
    down_mbps = result['download_bps'] / 1e6
    up_mbps = result['upload_bps'] / 1e6
    cp.log(f'Download: {down_mbps:.1f} Mbps, Upload: {up_mbps:.1f} Mbps')
```

### Engine Priority

1. **Ookla** (BYOB — Bring Your Own Binary) — fastest, requires separate license
2. **Netperf** (built-in) — no binary needed, no server config needed
3. **iPerf3** (user-provided server) — requires a server address

### Key Constraints

- **Netperf cannot run concurrent tests** — single shared router resource, test sequentially
- **Ookla and iPerf3 can run concurrently** — each is an independent subprocess
- Use `interface` parameter to route through specific modems

### Engine Detection Pattern

```python
import os

OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')

def has_ookla():
    for name in OOKLA_BINARIES:
        if os.path.exists(name):
            if not os.access(name, os.X_OK):
                os.chmod(name, 0o755)
            return True
    return False
```

---

## 14. GPIO

### Reading GPIO

```python
import cp

# Get all GPIOs for current router
gpios = cp.get_gpio()
cp.log(f'GPIOs: {gpios}')

# Get specific GPIO
power_in = cp.get_gpio('power_input')
cp.log(f'Power input: {power_in}')

# List available GPIOs
available = cp.get_available_gpios()
cp.log(f'Available: {available}')
```

### Writing GPIO (via config store)

```python
# Set GPIO output high
cp.put('config/gpio/CONNECTOR_OUTPUT', 1)

# Set GPIO output low
cp.put('config/gpio/CONNECTOR_OUTPUT', 0)
```

---

## 15. CLI Access (csterm) and Web Terminal (ttyd)

NCOS routers have a built-in CLI accessible via SSH. SDK apps can execute CLI commands programmatically using the **csterm** control tree, or provide a full web-based terminal using the **ttyd** binary.

### 15.1 CSTerm — Programmatic CLI Access

The `csterm.py` module (from the `cli_sample` app) lets your app execute NCOS CLI commands and capture their output. It works by writing commands to `control/csterm/{session_id}` and reading responses back.

#### Setup

Copy `csterm.py` from `apps/cli_sample/` into your app directory.

#### Basic Usage

```python
import cp
from csterm import CSTerm

cp.log('Starting...')

# Create a terminal session
ct = CSTerm(cp)

# Execute a single command
output = ct.exec('arpdump')
cp.log(f'ARP table:\n{output}')

# Execute multiple commands in sequence
output = ct.exec(['clients', 'arpdump'])
cp.log(output)
```

#### How It Works

1. CSTerm creates a unique session ID (`term-{random}`)
2. Commands are written to `control/csterm/{session_id}` with `cp.put()`
3. Responses are read from the same path with `cp.get()`
4. Output is polled at 0.3s intervals until a prompt is detected or timeout
5. ANSI escape sequences are stripped from the output (when `clean=True`)

#### CSTerm API

```python
CSTerm(csclient, timeout=10, soft_timeout=5, user=None)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `csclient` | required | The `cp` module (or any object with `get`/`put` methods) |
| `timeout` | 10 | Max seconds to wait for output |
| `soft_timeout` | 5 | Seconds before sending Ctrl+C to abort |
| `user` | None | CLI user to execute as (e.g., `"admin"`) |

```python
ct.exec(cmds, clean=True) -> str
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `cmds` | str or list | Single command string or list of commands |
| `clean` | bool | Strip ANSI escape sequences and prompt lines |
| **Returns** | str | Command output text |

#### Examples

**Run a single command:**
```python
ct = CSTerm(cp)
output = ct.exec('arpdump')
```

**Run multiple commands (same session):**
```python
output = ct.exec(['clients', 'arpdump', 'wan'])
```

**Multiple exec calls (persistent session state):**
```python
ct.exec('clients')
ct.exec('wan')
ct.exec('arpdump')
```

**SSH into a remote host through the router CLI:**
```python
ct = CSTerm(cp, timeout=30, soft_timeout=15)
output = ct.exec([
    'ssh user@192.168.1.100',
    'yes',           # Accept host key
    'password123',   # Enter password
    'ls -la',        # Run command on remote host
    'exit'           # Exit SSH
])
```

**Run as a specific user:**
```python
ct = CSTerm(cp, user="admin")
output = ct.exec('status')
```

**Longer-running commands (increase timeout):**
```python
ct = CSTerm(cp, timeout=30, soft_timeout=20)
output = ct.exec('ping 8.8.8.8 -c 10')
```

#### Common CLI Commands

| Command | Description |
|---------|-------------|
| `arpdump` | Show ARP table (connected devices) |
| `clients` | Show connected LAN clients |
| `wan` | Show WAN status |
| `status` | Show system status |
| `ping <host>` | Ping a host |
| `traceroute <host>` | Trace route to host |
| `log show` | Show system logs |
| `log show -s <app>` | Show logs for specific app |
| `sms <number> '<msg>' <port>` | Send SMS |
| `container list` | List running containers |

#### Using cp.execute_cli() Instead

The `cp` module also has a built-in `execute_cli()` function that provides similar functionality without needing the `csterm.py` file:

```python
import cp

# Single command
output = cp.execute_cli('arpdump')
cp.log(output)

# Multiple commands
output = cp.execute_cli(['clients', 'wan'])
cp.log(output)
```

The difference: `CSTerm` maintains a persistent session (stateful — like an interactive terminal), while `cp.execute_cli()` is stateless (each call is independent). Use `CSTerm` when you need multi-step interactions (SSH sessions, interactive commands) and `cp.execute_cli()` for simple one-off commands.

### 15.2 ttyd — Web-Based Terminal

The `ttyd` app provides a full Linux bash terminal accessible from any web browser on the LAN. It bundles the [ttyd](https://github.com/tsl0922/ttyd) binary — a terminal emulator served over HTTP/WebSockets.

#### What It Does

- Serves a full bash shell at `http://<router_ip>:8022`
- No SSH client needed — works in any modern browser
- WebSocket-based for real-time terminal interaction
- Access to the full NCOS Linux userland

#### App Structure

```
ttyd/
├── package.ini
├── start.sh          # Launches the binary directly (no cppython)
├── cp.py
├── csterm.py         # Optional — for programmatic access alongside
├── ttyd              # Statically linked ARM64 binary
└── readme.md
```

#### start.sh (Binary-Only App)

```bash
#!/bin/bash
./ttyd -p 8022 -W bash
```

Note: This app does NOT use `cppython`. The `start.sh` launches the `ttyd` binary directly. This is the **binary-only app pattern** — no Python code needed.

#### ttyd Flags

| Flag | Description |
|------|-------------|
| `-p 8022` | Listen on port 8022 |
| `-W` | Writable (allow keyboard input) |
| `bash` | Shell to spawn (bash is default on NCOS) |

#### How to Use

1. Deploy the app to the router
2. Open a browser: `http://<router_ip>:8022`
3. A terminal session opens — full bash access

#### Building Your Own ttyd App

If you want to bundle ttyd in your own app (e.g., alongside Python code):

1. Download the `ttyd` binary (ARM64/aarch64 static build) from [ttyd releases](https://github.com/tsl0922/ttyd/releases)
2. Place it in your app directory
3. Remember: tar extraction on the router does NOT preserve the execute bit. Set permissions before first use:

```python
import os
import subprocess
import cp

# Ensure binary is executable
ttyd_path = os.path.join(os.path.dirname(__file__), 'ttyd')
if os.path.exists(ttyd_path) and not os.access(ttyd_path, os.X_OK):
    os.chmod(ttyd_path, 0o755)

# Launch ttyd in background
subprocess.Popen(['./ttyd', '-p', '8022', '-W', 'bash'])
cp.log('Web terminal started on port 8022')
```

#### Security Considerations

- ttyd provides unauthenticated shell access to anyone on the LAN
- Consider using ttyd's `-c username:password` flag for basic auth:
  ```bash
  ./ttyd -p 8022 -W -c admin:secretpass bash
  ```
- Restrict access via router firewall zone rules if needed
- For production, consider limiting to specific interfaces or adding authentication

---

## 16. Containers on NCOS

Deploy Docker containers via the REST API:

```python
import cp
import json

compose_config = """version: "2.4"
services:
  myservice:
    image: myimage:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
volumes:
  mydata:
    driver: local
"""

project = {
    'name': 'my_project',
    'config': compose_config,
    'enabled': True,
    'update_interval': 0
}

cp.post('config/container/projects', json.dumps(project))
```

### Container Rules

| Rule | Detail |
|------|--------|
| Compose version | `"2.4"` (not v3) |
| Restart policy | `unless-stopped` (not `always`) |
| Named volumes | Must have `driver: local` |
| Memory limits | NOT supported (omit entirely) |
| Network mode | No `host` mode — use `ports:` instead |
| Images | Prefer `-alpine` variants (ARM64) |
| Shared memory | Set `shm_size: '1gb'` at service level if needed |

---

## 17. Local Development

Applications can run on your development machine. The `cp.py` module auto-detects the environment:

```bash
# Run locally — talks to router over REST
.venv/bin/python apps/my_app/my_app.py
```

### What Works Locally

| Feature | Behavior |
|---------|----------|
| `cp.get()` / `cp.put()` / `cp.post()` / `cp.delete()` | Routes through REST to dev router |
| `cp.log()` | Prints to stdout |
| All convenience functions using `cp.get()` | Work normally |
| Reading/writing appdata | Works via REST |

### What Does NOT Work Locally

| Feature | Behavior |
|---------|----------|
| `cp.alert()` | Logs to console, does not send to NCM |
| `cp.register()` / `cp.unregister()` | Requires router socket |
| `cp.decrypt()` | Returns None |
| Web servers (`http.server`) | Binds to YOUR machine, not router |
| Serial/GPIO | Accesses your computer, not router |

### Development Workflow

1. Edit code locally
2. Test logic with `python apps/my_app/my_app.py` (reads real data from router)
3. Deploy to router for final testing: `.venv/bin/python make.py deploy my_app`

---

## 18. Production Deployment via NCM

Once tested locally and on a dev router:

1. Build the package: `.venv/bin/python make.py build my_app`
2. Upload the `.tar.gz` to NetCloud Manager
3. Assign the application to a device group
4. NCM distributes and installs to all devices in the group

Apps can be configured per-group using appdata fields pushed from NCM.

---

## 19. Debugging and Troubleshooting

### Viewing Logs

```bash
# Check status and recent logs
.venv/bin/python make.py status my_app

# Or view via deploy output
.venv/bin/python make.py deploy my_app
```

### Router Log CLI (via SSH)

```bash
log show                    # Show all logs
log show -s my_app          # Filter by app name
log show -f                 # Follow (like tail -f)
log show -f 50              # Follow with last 50 lines
log show WARNING ERROR      # Filter by level
log clear                   # Clear all logs
```

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| App deleted after install | Modified a packaged file | Write only to NEW files |
| `Address already in use` | Port still bound | Set `SO_REUSEADDR`, or reboot router |
| `ModuleNotFoundError` | Missing dependency | `pip install -t my_app/ module` |
| `.so` or `.pyc` errors | Non-pure-Python files | Remove all `.so` and `.pyc` |
| App won't start | Wrong interpreter in start.sh | Use `cppython`, not `python3` |
| Stale logs | Old log buffer entries | Check timestamps — only trust entries after deploy |
| Deploy fails | Wrong credentials | Check `sdk_settings.ini` |
| SCP "lost connection" | Normal behavior | Router drops SSH after receiving file — expected |

### Error Handling Pattern

Always wrap API calls:

```python
try:
    data = cp.get('status/system')
    if data:
        cp.log(f"Uptime: {data.get('uptime')}")
except Exception as e:
    cp.log(f'Error: {e}')
```

---

## 20. Complete Examples

### Hello World

```python
# hello_world.py
import cp
cp.log('Hello World!')
```

### Signal Monitor with Alerts

```python
import cp
import time

RSRP_THRESHOLD = -110

cp.log('Starting signal monitor...')
cp.wait_for_wan_connection()

alerted = {}

while True:
    try:
        wans = cp.get_connected_wans()
        for uid in wans:
            signal = cp.get_signal_strength(uid)
            if signal:
                rsrp = signal.get('rsrp')
                if rsrp is not None and int(rsrp) < RSRP_THRESHOLD:
                    if not alerted.get(uid):
                        cp.alert(f'Low signal on {uid}: RSRP={rsrp} dBm')
                        alerted[uid] = True
                else:
                    alerted[uid] = False
    except Exception as e:
        cp.log(f'Error: {e}')
    time.sleep(300)
```

### MQTT Publisher

```python
import cp
import json
import time
from threading import Thread

try:
    import paho.mqtt.client as mqtt
except ImportError:
    cp.log('ERROR: paho-mqtt not installed')
    raise

BROKER = 'test.mosquitto.org'
PORT = 1883
TOPIC = 'router/status'
INTERVAL = 60

def on_connect(client, userdata, flags, rc):
    cp.log(f'MQTT connected: {mqtt.connack_string(rc)}')

def publish_loop(client):
    while True:
        try:
            data = {
                'uptime': cp.get_uptime(),
                'wan_state': cp.get_wan_connection_state(),
                'temperature': cp.get_temperature('celsius')
            }
            client.publish(TOPIC, json.dumps(data), qos=1)
            cp.log(f'Published to {TOPIC}')
        except Exception as e:
            cp.log(f'Publish error: {e}')
        time.sleep(INTERVAL)

cp.log('Starting MQTT app...')
cp.wait_for_wan_connection()

client = mqtt.Client(client_id=cp.get_name())
client.on_connect = on_connect
client.connect(BROKER, PORT)

Thread(target=client.loop_forever, daemon=True).start()
publish_loop(client)
```

### Web Dashboard with Auto-Refresh

```python
import cp
import json
import socket
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

PORT = 8000

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/data':
            data = {
                'system': cp.get_system_status(),
                'wan': cp.get_wan_status(),
                'gps': cp.get_gps_status(),
                'clients': cp.get_lan_clients()
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        elif self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass  # Suppress request logging

cp.log('Starting dashboard...')
server = HTTPServer(('', PORT), DashboardHandler)
server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
Thread(target=server.serve_forever, daemon=True).start()
cp.log(f'Dashboard running on port {PORT}')

while True:
    time.sleep(60)
```

### GPS Logger with Distance Threshold

```python
import cp
import json
import math
import time

MOVE_DISTANCE_M = 50
STATIONARY_INTERVAL = 300
POLL_INTERVAL = 5
GPS_LOG = 'gps_log.json'

def haversine(lat1, lon1, lat2, lon2):
    r = 6371000
    p = math.pi / 180
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))

cp.log('Starting GPS logger...')
cp.wait_for_wan_connection()

last_lat, last_lon = None, None
last_log_time = 0

while True:
    try:
        lat, lon = cp.get_lat_long()
        if lat is not None:
            now = time.time()
            should_log = False

            if last_lat is None:
                should_log = True
            else:
                dist = haversine(last_lat, last_lon, lat, lon)
                if dist >= MOVE_DISTANCE_M:
                    should_log = True
                elif (now - last_log_time) >= STATIONARY_INTERVAL:
                    should_log = True

            if should_log:
                entry = {'lat': lat, 'lon': lon, 'time': now}
                with open(GPS_LOG, 'a') as f:
                    f.write(json.dumps(entry) + '\n')
                cp.log(f'GPS: {lat}, {lon}')
                last_lat, last_lon, last_log_time = lat, lon, now
    except Exception as e:
        cp.log(f'GPS error: {e}')
    time.sleep(POLL_INTERVAL)
```

---

## Additional Resources

| Resource | Link |
|----------|------|
| App Store | [Browse & download apps](https://cradlepoint.github.io/sdk-samples/) |
| Official SDK Guide | [docs.cradlepoint.com](https://docs.cradlepoint.com/r/NCOS-SDK-Developers_Guide/) |
| GitHub Repository | [github.com/cradlepoint/sdk-samples](https://github.com/cradlepoint/sdk-samples) |
| NCM SDK Tools | [NCM Tools Tab](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab) |
| Pre-built Apps | [Releases](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps) |

---

*Copyright © 2026 Ericsson Enterprise Wireless Solutions. All rights reserved.*
