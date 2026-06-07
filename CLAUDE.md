# Cradlepoint SDK Development — Claude Code Instructions

This file provides Claude Code with the context, rules, and workflows needed to build Cradlepoint NCOS SDK applications in this repository.

## Project Overview

This is the Cradlepoint SDK samples repository. Applications are Python 3.8 scripts that run on Cradlepoint routers (ARM64, musl libc) using a custom Python runtime called `cppython`. The `cp` module provides access to router APIs.

## Environment Setup

Before any work, ensure the virtual environment exists:
```bash
python3 make.py setup  # Creates .venv and installs dependencies
```

If `.venv` doesn't exist, run setup first.

## Configuration

Router connection settings are in `sdk_settings.ini`:
```ini
[sdk]
app_name=your_app_name
dev_client_ip=192.168.1.4
dev_client_username=admin
dev_client_password=your_password
```

**ALWAYS check sdk_settings.ini before deploying** — if `dev_client_password=mypassword`, warn the user to update it.

---

## Coding Standards (Python 3.8)

### Language Constraints
- **NEVER use `str | None`** — use `Optional[str]` from typing
- **NEVER use walrus operator `:=`**
- Use 4 spaces, PEP 8, lines under 100 chars
- Never use bare `except:` — always catch specific exceptions or `Exception`
- **ALWAYS use try/except** — never raise exceptions that crash the app

### Router Environment
- **No screen** — use `cp.log()` for all output (never `print()`)
- **No keyboard** — never use `input()` or `KeyboardInterrupt`
- **Relative paths only** — use `tmp/`, never `/tmp`
- **Create directories before writing** — `os.makedirs('tmp', exist_ok=True)`
- **Python is "cppython"** — `start.sh` must use `cppython`
- **Boot logging** — `cp.log('Starting...')` ASAP at startup
- **Wait for connectivity** — use `cp.wait_for_wan_connection()` if internet is needed
- **NEVER modify packaged files** — digital signatures prevent it. Write to NEW files only
- **NEVER write default values to appdata** — this overrides NCM group configs
- **Router architecture is ARM64 (aarch64) with musl libc**

### JavaScript (for web UIs)
- **ALWAYS use ES5** — NO arrow functions `=>`, NO template literals, NO `let`/`const`
- Use `function(){}` for all functions
- Use string concatenation `'text' + var + 'more'` instead of template literals
- **NEVER pass parameters in onclick attributes** — use data attributes and `this`

### Web Development
- **ALWAYS use Python's built-in `http.server`** — never Flask, Bottle, etc.
- Default port: 8000
- **ALWAYS set SO_REUSEADDR** before binding
- Run HTTP server in a daemon thread
- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- Copy `static/` from `web_app_template/` for the design system
- Copy `your_web_app.html` from `web_app_template/` as starting HTML

---

## CP Module API Reference

### Core Functions
```python
import cp

# CRUD operations — cp.get() returns data directly, NOT wrapped in {"success": true, "data": ...}
cp.get('status/path')          # Read status/config
cp.put('config/path', value)   # Update config
cp.post('config/path', value)  # Create new entry
cp.delete('config/path')       # Delete entry
cp.put('control/path', value)  # Trigger actions

# Logging and alerts
cp.log('message')              # Syslog output (stdout locally)
cp.alert('message')            # NCM alert (NOT available locally)

# Event registration (NOT available locally)
cp.register('put', 'control/path', callback)  # MUST use lowercase 'put'
cp.unregister(event_id)

# Appdata (user-configurable values stored in config/system/sdk/appdata)
cp.get_appdata('field_name')   # Get single field value (string)
cp.put_appdata('name', 'val')  # TWO args: name and value as separate strings
cp.post_appdata('name', 'val') # Create new appdata field
cp.delete_appdata('name')      # Delete appdata field

# Utilities
cp.wait_for_wan_connection(timeout=300)  # Block until WAN is up
cp.get_lat_long()              # Returns (lat, lon) tuple
cp.get_sims()                  # Returns list of modem UID strings
cp.get_wan_profiles()          # Returns list of WAN profile dicts
```

### Key Gotchas
- `cp.get()` returns data directly — never do `cp.get('path').get('data')`
- `cp.get_appdata('field')` — ALWAYS pass a field name. Without args returns a list of dicts
- `cp.put_appdata(name, value)` — TWO arguments, not a dict
- `cp.register()` MUST use `'put'` (lowercase) as action for control tree
- Do NOT `cp.put()` to seed control tree before `cp.register()` — causes socket desync
- Control tree keys persist across app redeploys
- `status/lan/clients` does NOT have rx_bytes/tx_bytes — use `status/client_usage`

### Common API Patterns
```python
# System health
sys = cp.get('status/system')
cpu_percent = (sys.get('cpu', {}).get('user', 0) + sys.get('cpu', {}).get('system', 0)) * 100

# WAN state
state = cp.get('status/wan/connection_state')  # 'connected' or 'disconnected'
primary = cp.get('status/wan/primary_device')  # device name string

# WAN devices (dict keyed by UID)
devices = cp.get('status/wan/devices') or {}
for uid, dev in devices.items():
    diag = dev.get('diagnostics', {})
    # Signal: diag['DBM'], diag['RSRP'], diag['SINR'], diag['CARRID']

# LAN clients
clients = cp.get('status/lan/clients') or []  # [{'ip_address', 'mac', 'hostname'}]

# GPIO
cp.put('control/gpio/LED_SS_0', 1)  # On
cp.get('status/gpio')                # Read all GPIO states

# Reboot
cp.put('control/system/reboot', 1)
```

---

## NCOS API Documentation

Full API docs are in `docs/ncos-api/`:
- `docs/ncos-api/README.md` — Quick reference with common tasks
- `docs/ncos-api/api-structures.md` — All response formats and patterns
- `docs/ncos-api/status/` — Status API (read-only): WAN, GPS, modem, system
- `docs/ncos-api/config/PATHS.md` — 500+ configuration paths
- `docs/ncos-api/control/` — Control API (actions): reboot, ping, GPIO

### API Verification Workflow (RTFM)

**BEFORE writing ANY code that uses an API path:**
1. Search docs: `grep -r "keyword" docs/ncos-api/ --include="*.md"`
2. Read relevant docs for usage patterns
3. Check DTD: `curl -s -u admin:pass http://ROUTER/api/dtd/config/path | python3 -m json.tool`
4. Test with curl: `curl -s -u admin:pass http://ROUTER/api/status/path | python3 -m json.tool`
5. Verify fields exist in the response
6. THEN write code

**NEVER assume API fields exist without testing.**

---

## Project Structure

```
app_name/
├── package.ini          # Metadata: uuid, version, vendor
├── cp.py               # CP module (auto-generated, NEVER modify)
├── {app_name}.py       # Main logic
├── start.sh            # Uses cppython (auto-generated, NEVER modify)
├── readme.md           # Usage docs and appdata fields
├── static/             # Web assets (if web app)
└── mylib/              # Subdirectories with Python modules work fine
```

---

## Workflow Commands

### Create an App
```bash
.venv/bin/python make.py create {app_name}
```
This generates package.ini, start.sh, cp.py, {app_name}.py, readme.md.

**After creation, only modify `{app_name}.py` and `readme.md`** — other files are generated correctly.

### Deploy to Router
```bash
.venv/bin/python make.py deploy {app_name}
```
This purges old apps, builds, installs, starts, and shows logs. **ALWAYS deploy after any code change.**

**NEVER use `make.py install` directly** — always use `deploy`.

### Other Commands
```bash
.venv/bin/python make.py status {app_name}
.venv/bin/python make.py start {app_name}
.venv/bin/python make.py stop {app_name}
.venv/bin/python make.py uninstall {app_name}
.venv/bin/python make.py clean {app_name}
```

### Local Development
Apps can run locally: `.venv/bin/python my_app/my_app.py`
- cp.get/put/post/delete work via REST to the dev router
- cp.log() prints to stdout
- cp.alert(), cp.register(), cp.decrypt() do NOT work locally
- Web servers bind to YOUR machine, not the router

---

## Auto-Deploy Rule

**ALWAYS deploy after creating or modifying an app.** After any code change to app Python files, automatically run:
```bash
.venv/bin/python make.py deploy {app_name}
```
Do NOT ask the user if they want to deploy — just do it.

---

## Self-Improvement (Learning Loop)

After each task, reflect:
- Did you discover an API returns different data than documented?
- Did you find a field that doesn't exist or works differently?
- Did you make wrong assumptions?

If yes, update the appropriate file:
- **This file (CLAUDE.md)** — for rules, guardrails, quick reference
- **`docs/ncos-api/`** — for detailed API examples and structures

Only document GENERAL learnings (API behavior, router constraints, SDK patterns). Do NOT document app-specific logic.

---

## Libraries and Dependencies

- Install to app folder: `.venv/bin/pip install -t path/to/app_folder library_name`
- **No .pyc or .so files** — routers only support pure Python
- `cppython` is missing: `pkg_resources`, `decimal`, `csv` (copy shims from 5GSpeed if needed)
- `cppython` HAS: `threading`, `ssl`, `http.server`, `socket`, `configparser`, `json`, `os`, `sys`, `time`, `xml.etree.ElementTree`, `hashlib`, `base64`, `uuid`, `logging`, `struct`
- For CSV: prefer `','.join(fields) + '\n'` over the csv module
- For NMEA parsing: use `pynmeagps` (install fresh, never copy from other apps)
- For speedtest: copy `speedtest_ookla.py` and `ookla` binary from `5GSpeed/`

---

## Docker/Container Development

- Deploy via REST API: `POST /api/config/container/projects/`
- Use Compose version `"2.4"` (NOT v3)
- Named volumes MUST have `driver: local`
- Use `restart: unless-stopped` (NOT `always`)
- NO `network_mode: host` — use `ports:` instead
- NO memory limits — runtime doesn't support them
- Prefer alpine-based images

---

## Error Handling Pattern

```python
import cp
cp.log('Starting...')

try:
    data = cp.get('status/system')
    if data:
        # process data
        pass
except Exception as e:
    cp.log(f'Error: {e}')
```

---

## GPS/NMEA

- Use `pynmeagps` for parsing — never write custom parsers
- Data sources: `status/gps/nmea` (array), `status/gps/devices/{uid}/current_nmea`
- Skip `PCPTMINR` sentences (proprietary, raises "Unknown msgID")
- Speed from RMC: `speed_kmh = msg.spd * 1.852`

---

## Key Files to Reference

| File | Purpose |
|------|---------|
| `app_template/` | Standard app skeleton |
| `web_app_template/` | Web app skeleton with UI framework |
| `5GSpeed/speedtest_ookla.py` | Ookla speedtest wrapper |
| `docs/ncos-api/README.md` | API quick reference |
| `docs/ncos-api/api-structures.md` | Detailed API response formats |
| `docs/ncos-api/config/PATHS.md` | All config paths |
| `sdk_settings.ini` | Router connection settings |
| `make.py` | Build/deploy tool |
