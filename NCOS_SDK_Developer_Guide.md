# Ericsson (Cradlepoint) NetCloud OS SDK Developer Guide

A practical reference for network engineers building Python applications on Ericsson Cradlepoint routers.

---

## 1. Introduction

The NetCloud OS (NCOS) SDK enables you to write Python applications that run directly on Ericsson Cradlepoint routers. These applications execute on the device itself, giving you programmatic access to modem diagnostics, WAN status, GPS, LAN clients, GPIO, and the full NCOS configuration and status tree — without additional hardware.

Use cases include automated site surveys, signal monitoring, data forwarding to cloud platforms (Splunk, Azure IoT, MQTT brokers), custom dashboards, OBD-II vehicle telemetry, geofencing, bandwidth management, and IoT device integration via serial or USB.

Applications are deployed either directly to a development device over SSH or at scale through Ericsson NetCloud Manager (NCM) using group-based assignment.

### What the SDK Supports

- TCP/UDP/SSL socket servers (ports above 1024) and clients
- Serial port access via PySerial (native and USB-serial)
- ICMP ping to external hosts
- Custom web interfaces (hotspot splash pages, dashboards, admin tools)
- Full read/write access to the NCOS API (status, config, and control trees)
- USB storage file access
- Container deployment via Docker Compose

### What Is Not Supported

- Compiled Python bytecode (`.pyc`) and dynamically linked shared objects (`.so`) used as Python modules
- Any operation requiring root or privileged permissions
- Python standard library modules not included in the NCOS environment (see Section 4)

Statically linked ARM64 (aarch64) ELF binaries *are* supported and can be bundled directly in your application package. See Section 5.5 for details.

### Support Policy

Ericsson publishes and supports the SDK toolkit. However, custom applications built with the SDK are the sole responsibility of the developer. Ericsson does not develop, maintain, or guarantee continued compatibility of third-party SDK applications across NCOS firmware releases. Test thoroughly before production deployment.

---

## 2. Development Environment Setup

### Prerequisites

- Python 3.8 or later on your development machine (Windows users: see [WINDOWS_PYTHON_SETUP.md](WINDOWS_PYTHON_SETUP.md) for detailed install steps)
- OpenSSL tools (for application signing)
- SSH access to a Cradlepoint router in Developer Mode (enabled via NetCloud Manager, not the router UI)

### SDK Installation

Clone the SDK and install Python dependencies:

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

This creates a `.venv` virtual environment and installs all Python dependencies from `requirements.txt` automatically.

Using [Kiro](https://kiro.dev)? See [docs/SETUP.md](docs/SETUP.md) for a guided walkthrough — the Python environment is set up automatically.

To activate the virtual environment later:

```bash
# Windows
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### System-Level Dependencies (manual, one-time)

The setup scripts handle Python libraries, but some system-level tools must be installed separately.

#### Windows

1. Install OpenSSL (Light version) from [slproweb.com](https://slproweb.com/products/Win32OpenSSL.html). Choose Win64 or Win32 based on your machine.

#### macOS

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"

# Required for app signing and device deployment
brew install openssl
brew install hudochenkov/sshpass/sshpass
```

#### Linux (Debian/Ubuntu)

```bash
sudo apt-get install libffi-dev libssl-dev sshpass python3-pip
```

### Recommended Tools

- A terminal with SSH/SCP support (PuTTY on Windows, native terminal on macOS/Linux)

### Running Applications Locally

You can run SDK applications directly on your development machine using standard Python. The `cp.py` module automatically detects whether it is running on a router (via the presence of `/var/tmp/cs.sock`) or on a computer. When running locally, all `cp.get()`, `cp.put()`, `cp.post()`, and `cp.delete()` calls are sent as HTTP REST requests to the router specified in `sdk_settings.ini`.

This means you can develop and test most application logic without deploying to the router on every change:

```bash
# Run your app locally — it talks to the router over REST
python3 my_app/my_app.py
```

#### What Works Locally

- `cp.get()` / `cp.put()` / `cp.post()` / `cp.delete()` — all route through REST to the dev router
- `cp.log()` — prints to stdout (console) instead of syslog
- All convenience functions that use `cp.get()` internally (e.g., `cp.get_lat_long()`, `cp.get_connected_wans()`, `cp.get_signal_strength()`)
- Reading and writing appdata

#### What Does Not Work Locally

| Function | Behavior When Local |
|----------|-------------------|
| `cp.alert()` | Logs the alert text to console but does not send to NCM |
| `cp.register()` / `cp.unregister()` | Event callbacks require the router's socket — no REST equivalent |
| `cp.decrypt()` | Logs a message and returns `None` — decryption requires the router |
| Web servers (`http.server`) | Binds to your local machine's port, not the router's — LAN clients cannot reach it |
| Serial port access | Accesses your computer's serial ports, not the router's |
| GPIO | Not available on your computer |
| `cppython`-specific modules | Your local Python may have different modules than the router |

#### Local Development Tips

- Use `sdk_settings.ini` to point at your dev router — `cp.py` reads credentials from there automatically.
- Test your core logic (API reads, data processing, decision-making) locally for fast iteration.
- Deploy to the router for final testing of alerts, event registration, web UIs, serial, and GPIO.
- `cp.log()` output goes to your terminal when local, so you get immediate feedback.

---

## 3. Application Structure

Every SDK application follows a consistent directory layout:

```
my_app/
├── package.ini        # Application metadata (UUID, version, vendor)
├── start.sh           # Entry point — must use cppython
├── cp.py              # SDK communication library (do not modify)
├── my_app.py          # Your application logic
└── readme.md          # Documentation and appdata field descriptions
```
### package.ini

Defines application metadata used by the router and NetCloud Manager:

```ini
[my_app]
uuid =
vendor = Ericsson/Cradlepoint
notes = SDK Application
version_major = 1
version_minor = 0
version_patch = 0
auto_start = true
restart = true
reboot = true
firmware_major = 7
firmware_minor = 25
```

The `uuid` field is auto-generated when you create the app with `make.py`. The `auto_start`, `restart`, and `reboot` flags control whether the app starts automatically, restarts on crash, and survives device reboots.

### start.sh

The entry point script. It must use `cppython` (the router's Python interpreter), not `python` or `python3`:

```bash
#!/bin/bash
cppython my_app.py
```

### cp.py

The SDK communication library. This file is auto-generated and should not be modified. It provides the `cp` module your application imports to interact with the router.

---

## 4. The NCOS Python Environment

The router runs Python 3.8 via `cppython`, which is a constrained subset of a standard Python installation. Understanding these constraints is essential before writing code.

### Available Standard Library Modules

These modules are confirmed available on NCOS devices:

`threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`, `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`, `time`, `xml.etree.ElementTree`

### Missing Standard Library Modules

These common modules are not available in `cppython`:

`pkg_resources`, `decimal`, `csv`

If your application or a dependency requires these, copy the pure-Python shim files from existing sample apps (e.g., `decimal.py`, `csv.py`, `_csv.py` from the `5GSpeed` or `Mobile_Site_Survey` directories).

### Adding Third-Party Libraries

Install libraries directly into your application directory:

```bash
pip3 install --target=my_app/ library_name
```

After installation, delete any `egg-info` or `dist-info` directories — they consume storage and are not needed at runtime.

Constraints:
- Only pure Python (`.py`) files are supported. Remove any `.pyc` or `.so` files.
- Libraries must be compatible with Python 3.8.
- Keep dependencies minimal — app size limit is 60MB archive.

### Python 3.8 Syntax Restrictions

Since the runtime is Python 3.8, avoid newer syntax:

```python
# Do NOT use union type syntax (Python 3.10+)
# value: str | None = None        # WRONG

# Use Optional instead
from typing import Optional
value: Optional[str] = None       # CORRECT
```

---

## 5. The cp Module — Router API Access

The `cp` module is your primary interface to the router. Import it at the top of your application:

```python
import cp
```

### Logging

There is no screen or console on the router. Use `cp.log()` for all output — never `print()`:

```python
cp.log('Starting my_app...')
```

Log output is visible in NetCloud Manager and via `make.py` during development.

### Reading Router Data

Use `cp.get()` to read from the status and config trees:

```python
# Get system status
system = cp.get('status/system')

# Get modem signal information
wan_devices = cp.get('status/wan/devices')

# Get GPS coordinates
lat, lon = cp.get_lat_long()
cp.log(f'Location: {lat}, {lon}')
```

### Writing Configuration

Use `cp.put()` to modify configuration and `cp.post()` to create new entries:

```python
# Set the device description
cp.put('config/system/asset_id', 'Site-42-Router')

# Trigger a control action
cp.put('control/system/reboot', '')
```

### Sending Alerts

Send alerts visible in NetCloud Manager:

```python
cp.alert('WAN failover detected — switched to LTE backup')
```

### Waiting for Connectivity

If your app needs internet access, wait for a WAN connection before proceeding:

```python
cp.wait_for_wan_connection()
cp.log('WAN is up, proceeding...')
```

### Application Data (appdata)

Appdata provides per-app key-value storage configurable from NetCloud Manager. Use it for user-configurable settings:

```python
# Read a setting
server_url = cp.get_appdata('server_url')
if not server_url:
    server_url = 'https://default.example.com'  # Code default, not written to appdata
    cp.log('No server_url configured, using default')

# Write a value
cp.put_appdata('last_run', '2025-01-15T10:30:00')
```

Never write default values to appdata — doing so overrides group-level configurations pushed from NCM.

### Event Registration

Register callbacks that fire when specific API paths change:

```python
def on_wan_change(path, value, args):
    cp.log(f'WAN state changed: {value}')

cp.register('set', 'status/wan/connection_state', on_wan_change)
```

Note: The callback receives exactly three arguments: `(path, value, args)` where `args` is a single tuple.

### Convenience Functions

The `cp` module includes many high-level helpers. A selection of commonly used ones:

| Function | Description |
|----------|-------------|
| `cp.get_lat_long()` | Returns `(latitude, longitude)` tuple |
| `cp.get_uptime()` | Router uptime in seconds |
| `cp.get_connected_wans()` | List of connected WAN interface names |
| `cp.get_sims()` | SIM card details for all slots |
| `cp.get_ipv4_lan_clients()` | Connected LAN clients by interface |
| `cp.get_signal_strength(uid)` | Modem signal metrics (RSRP, RSRQ, SINR) |
| `cp.get_temperature()` | Device temperature |
| `cp.get_power_usage()` | Power consumption data |
| `cp.get_wan_device_summary()` | Summary of all WAN devices and states |
| `cp.get_firmware_version()` | Current NCOS firmware version |
| `cp.get_serial_number()` | Device serial number |
| `cp.get_mac()` | Device MAC address |
| `cp.ping_host(host)` | Ping a remote host |
| `cp.reset_modem()` | Reset the cellular modem |
| `cp.get_ncm_api_keys()` | Retrieve NCM API credentials |
| `cp.extract_cert_and_key(name)` | Extract TLS certificate and private key |

For the complete API reference, see [cp_methods_reference.md](https://github.com/cradlepoint/sdk-samples/blob/master/cp_methods_reference.md).

### 5.5 Bundling Native Binaries

SDK applications can include statically linked ARM64 ELF binaries alongside (or instead of) Python code. The router's architecture is ARM64 (aarch64) with musl libc.

#### Requirements

- The binary must be a statically linked, 64-bit ARM aarch64 ELF executable.
- Do not use dynamically linked binaries — the router does not have a standard Linux userland with shared libraries.
- Verify your binary before packaging:

```bash
file my_binary
# Expected: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, stripped
```

#### Binary-Only Application (no Python)

An application can consist entirely of a native binary with no Python code. In this case, `start.sh` launches the binary directly instead of `cppython`:

```
ttyd/
├── package.ini
├── start.sh          # Launches the binary directly
├── cp.py             # Still included (auto-generated)
├── ttyd              # Statically linked ARM64 binary
└── readme.md
```

```bash
# start.sh — binary-only app
#!/bin/bash
./ttyd -p 8022 -W bash
```

#### Mixed Application (Python + Binary)

More commonly, a Python application invokes a bundled binary using `subprocess` or `os.system`. The binary is placed in the application directory and called with a relative path:

```
my_app/
├── package.ini
├── start.sh          # cppython my_app.py
├── cp.py
├── my_app.py         # Python logic that invokes the binary
├── my_binary         # Statically linked ARM64 binary
└── readme.md
```

```python
import cp
import subprocess

cp.log('Running binary...')
try:
    result = subprocess.run(['./my_binary', '--arg1', 'value'],
                            capture_output=True, text=True, timeout=120)
    cp.log(f'Output: {result.stdout}')
    if result.returncode != 0:
        cp.log(f'Error: {result.stderr}')
except Exception as e:
    cp.log(f'Binary execution failed: {e}')
```

#### Where to Find ARM64 Binaries

When sourcing binaries for NCOS applications, always download the `aarch64`, `arm64`, or `linux-arm64` variant. Do not use `x86_64` or `amd64` builds. Many open-source projects publish static ARM64 builds on their GitHub releases pages.

---

## 6. Error Handling

Robust error handling is critical on embedded devices where failures must not crash the application.

### General Pattern

Wrap all API calls and external operations in try/except blocks:

```python
try:
    data = cp.get('status/system')
    if data:
        cp.log(f"System ID: {data.get('system_id', 'unknown')}")
except Exception as e:
    cp.log(f'Error reading system status: {e}')
```

### Rules

- Never use bare `except:` — always catch a specific exception or `Exception`.
- Never use `input()` or `KeyboardInterrupt` — there is no keyboard.
- Log errors with enough context to diagnose the issue remotely.

---

## 7. File System Considerations

### Digital Signatures

Every packaged application includes a `MANIFEST.json` with digital signatures. If any packaged file is modified at runtime, the router deletes the entire application. Always write to new files that were not part of the original package.

### Path Rules

- Use relative paths only (e.g., `data/results.json`, not `/tmp/results.json`).
- Create directories before writing with `os.makedirs('data', exist_ok=True)`.
- Any directory name is fine — just ensure it does not overwrite packaged files.

### State Persistence

Save application state to survive reboots:

```python
import json, os

STATE_FILE = 'state.json'

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
```

## 8. Web Applications

SDK apps can serve web interfaces accessible from the router's LAN.

### Basic Web Server Pattern

```python
import cp
import json
import socket
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

server = HTTPServer(('', PORT), MyHandler)
server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

Thread(target=server.serve_forever, daemon=True).start()
cp.log(f'Web server started on port {PORT}')

# Main application loop
while True:
    time.sleep(60)
```

### Web Development Rules

- Default to port 8000.
- Always set `SO_REUSEADDR` before binding to avoid "Address in use" errors on redeployment.
- Run the HTTP server in a daemon thread so the main thread can handle application logic.
- Serve all assets locally (CSS, JS, images). Do not reference external CDNs — the router may not always have internet access.
- All static files (HTML, CSS, JS) go in the application directory alongside your Python files.

---

## 9. Building and Deploying Applications

### Creating a New Application

```bash
python3 make.py create my_app
```

This generates all required files from the `app_template` directory. After creation, edit only `my_app.py` and `readme.md` — do not modify `package.ini`, `start.sh`, or `cp.py`.

### SDK Settings

Configure `sdk_settings.ini` in the repository root with your development router's connection details:

```ini
[sdk]
app_name=my_app
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password_here
```

### Build and Install

```bash
# Build the application package
python3 make.py build my_app

# Install to a locally connected router (must be in Developer Mode)
python3 make.py install my_app

# Check application status
python3 make.py status
```

The build process creates a `.tar.gz` package containing all files in the application directory. This same package format is used for both local development and NCM deployment.

### Application Lifecycle Commands

| Command | Description |
|---------|-------------|
| `python3 make.py create my_app` | Scaffold a new application |
| `python3 make.py build my_app` | Build the `.tar.gz` package |
| `python3 make.py install my_app` | Deploy to development router |
| `python3 make.py start my_app` | Start the application |
| `python3 make.py stop my_app` | Stop the application |
| `python3 make.py status` | Check status of all installed apps |
| `python3 make.py uninstall my_app` | Remove from router |
| `python3 make.py purge` | Remove all installed applications from router |
| `python3 make.py clean my_app` | Remove local build artifacts |

### Production Deployment via NetCloud Manager

Once your application is tested locally:

1. Build the `.tar.gz` package with `make.py build`.
2. Upload the package to NetCloud Manager.
3. Assign the application to a device group.
4. NCM distributes and installs the application to all devices in the group.

### Build Ignore

Exclude files from the built package by creating a `buildignore` file in your app directory:

```
# Development files
test_data.json
requirements.txt

# Directories
tests/
docs/
```

The following are always excluded automatically: `__pycache__/`, `buildignore`, `.DS_Store`.

---

## 10. Practical Examples

### Read Appdata Configuration

```python
import cp

cp.log('Starting configurable app...')

# Read user-configurable values from NCM appdata
interval = cp.get_appdata('poll_interval')
interval = int(interval) if interval else 30  # Default 30 seconds

target = cp.get_appdata('target_host')
if not target:
    target = '8.8.8.8'
    cp.log('No target_host configured, using default')

cp.log(f'Polling {target} every {interval}s')
```

### Monitor Signal Strength and Alert on Degradation

```python
import cp
import time

RSRP_THRESHOLD = -110  # dBm

cp.log('Starting signal monitor...')
cp.wait_for_wan_connection()

alerted = {}  # Track which WANs have already triggered an alert

while True:
    try:
        wans = cp.get_connected_wans()
        for wan_id in wans:
            signal = cp.get_signal_strength(wan_id)
            if signal:
                rsrp = signal.get('rsrp')
                if rsrp is not None and rsrp < RSRP_THRESHOLD:
                    if not alerted.get(wan_id):
                        cp.alert(f'Low signal on {wan_id}: RSRP={rsrp} dBm')
                        cp.log(f'Alert sent: {wan_id} RSRP={rsrp}')
                        alerted[wan_id] = True
                else:
                    if alerted.get(wan_id):
                        cp.alert(f'Signal recovered on {wan_id}: RSRP={rsrp} dBm')
                        cp.log(f'Recovery alert sent: {wan_id} RSRP={rsrp}')
                        alerted[wan_id] = False
    except Exception as e:
        cp.log(f'Error in signal monitor: {e}')
    time.sleep(300)
```

### Log GPS Position by Distance or Time

Logs a GPS point every time the device moves a configurable distance, or at a slower interval while stationary. All thresholds are configurable via appdata.

```python
import cp
import json
import math
import time

# Defaults — override via NCM appdata
MOVE_DISTANCE_M = 50     # Log when moved this many meters
STATIONARY_DIST_M = 10   # Movement below this is considered stationary
STATIONARY_INTERVAL = 300 # Seconds between logs while stationary
POLL_INTERVAL = 5         # Seconds between GPS checks

GPS_LOG = 'gps_log.json'


def haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS coordinates."""
    r = 6371000
    p = math.pi / 180
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def load_config():
    """Load thresholds from appdata, fall back to defaults."""
    move = cp.get_appdata('move_distance_m')
    stat_dist = cp.get_appdata('stationary_dist_m')
    stat_int = cp.get_appdata('stationary_interval')
    return (
        int(move) if move else MOVE_DISTANCE_M,
        int(stat_dist) if stat_dist else STATIONARY_DIST_M,
        int(stat_int) if stat_int else STATIONARY_INTERVAL,
    )


def write_entry(lat, lon):
    entry = {'lat': lat, 'lon': lon, 'time': time.time()}
    with open(GPS_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    cp.log(f'GPS logged: {lat}, {lon}')


cp.log('Starting GPS logger...')
cp.wait_for_wan_connection()

last_lat, last_lon = None, None
last_log_time = 0

while True:
    try:
        move_dist, stat_dist, stat_interval = load_config()
        lat, lon = cp.get_lat_long()
        if lat is not None and lon is not None:
            now = time.time()
            if last_lat is None:
                write_entry(lat, lon)
                last_lat, last_lon, last_log_time = lat, lon, now
            else:
                dist = haversine(last_lat, last_lon, lat, lon)
                if dist >= move_dist:
                    # Moved — log immediately
                    write_entry(lat, lon)
                    last_lat, last_lon, last_log_time = lat, lon, now
                elif dist < stat_dist and (now - last_log_time) >= stat_interval:
                    # Stationary — log on timer
                    write_entry(lat, lon)
                    last_log_time = now
    except Exception as e:
        cp.log(f'GPS error: {e}')
    time.sleep(POLL_INTERVAL)
```

---

## 11. Containers on NCOS

Cradlepoint routers support Docker containers via the NCOS container runtime, deployed through the REST API.

### Key Constraints

- Use `restart: unless-stopped` (not `restart: always`).
- Named volumes require explicit `driver: local`.
- Memory limit directives (`mem_limit`, `deploy.resources.limits.memory`) are not supported. Set `shm_size' at the service level to set shared memory size.
- Prefer alpine-based images to minimize storage and RAM usage.
- Router architecture is ARM64 (aarch64) with musl libc — use `arm64` image variants.

### Deploying a Container via SDK

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
cp.log('Container project deployed')
```

---

## 12. Debugging and Troubleshooting

### Viewing Logs

Application logs are accessible through:
- `make.py status` — shows status of all installed apps
- NetCloud Manager — device logs section
- SSH to the router — use the `log` CLI command

#### Router Log CLI

The router uses a `log` command (not `/var/log/messages`). Common usage:

```bash
# Show all logs
log show

# Filter by app name or search string
log show -s my_app

# Follow logs in real time (like tail -f)
log show -f

# Follow with history (last 50 lines + new)
log show -f 50

# Case-insensitive search
log show -i -s "error"

# Highlight matches without filtering
log show -h -s my_app

# Filter by log level
log show WARNING ERROR

# Clear all logs
log clear
```

#### Log Levels

```bash
# View current log level
log level

# Set log level
log level DEBUG

# View all service log levels
log service

# Change a specific service log level
log service level DEBUG
```

#### Writing to the Log from CLI

```bash
# Write a message (defaults to INFO level)
log msg "Test message from CLI"

# Write at a specific level
log msg -l WARNING "Something needs attention"
```

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| App deleted after install | Modified a packaged file at runtime | Write only to new files (e.g., `tmp/`) |
| `Address already in use` | Port still bound from previous deploy | Set `SO_REUSEADDR`, or reboot the router |
| `ModuleNotFoundError` | Missing dependency | `pip3 install --target=my_app/ module_name` |
| `.so` or `.pyc` errors | Non-pure-Python files in app | Remove all `.so` and `.pyc` files |
| App won't start | `start.sh` uses `python3` instead of `cppython` | Edit `start.sh` to use `cppython` |
| Stale log entries | Reading old log buffer | Check timestamps — only trust entries after your deploy |

### Development Workflow

1. Edit your application code locally.
2. Build and deploy: `python3 make.py build my_app && python3 make.py install my_app`
3. Check status: `python3 make.py status`

---

## 13. Additional Resources

| Resource | URL |
|----------|-----|
| SDK GitHub Repository | [github.com/cradlepoint/sdk-samples](https://github.com/cradlepoint/sdk-samples) |
| Official SDK Developer Guide | [docs.cradlepoint.com](https://docs.cradlepoint.com/r/NCOS-SDK-Developers_Guide/) |
| cp Module API Reference | [cp_methods_reference.md](https://github.com/cradlepoint/sdk-samples/blob/master/cp_methods_reference.md) |
| Developer Community Portal | [dev.cradlepoint.com](http://dev.cradlepoint.com/) |
| Customer Community Forums | [customer.cradlepoint.com](http://customer.cradlepoint.com/s/) |
| NetCloud Manager SDK Tools | [NCM Tools Tab](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab) |
| SDK Support Statement | [SDK Support](https://docs.cradlepoint.com/r/NCOS-SDK) |
| Pre-built Sample Apps | [Releases](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps) |
