# Cradlepoint NCOS SDK — AI Coding Conventions

This file defines coding standards, API reference, and workflow rules for building SDK applications on Ericsson Cradlepoint routers running NetCloud OS (NCOS).

**Detailed API documentation**: See `docs/ncos-api/` for full endpoint reference, response structures, and code examples.

---

## Python 3.8 Constraints

- NEVER use `str | None` syntax — use `Optional[str]` from typing
- NEVER use walrus operator (`:=`) in complex expressions
- NEVER use `match`/`case` statements
- Use 4 spaces, follow PEP 8, keep lines under 100 chars
- Never use bare `except:` clauses — always catch specific exceptions or `Exception`

---

## Router Environment

- **No screen** — use `cp.log()` for all output. Never use `print()`
- **No keyboard** — never use `input()` or `KeyboardInterrupt`
- **Relative paths only** — use `tmp/`, never `/tmp`
- **Create directories before writing** — `os.makedirs('tmp', exist_ok=True)`
- **Python is "cppython"** — `start.sh` must use `cppython`
- **No .pyc or .so files** — only pure Python (.py) supported
- **Boot logging** — `cp.log('Starting...')` immediately at startup
- **Wait for connectivity** — use `cp.wait_for_wan_connection()` if internet needed
- **NEVER modify packaged files** — router deletes app if any packaged file changes. Write to NEW files only
- **NEVER write default values to appdata** — overrides NCM group configs. Read appdata, use code default if missing
- **Architecture** — ARM64 (aarch64) with musl libc

---

## CP Module Usage

- Always `import cp` and use module-level functions
- Never use EventingCSClient or CSClient classes
- **Check cp.py for helper functions before using direct API calls**
- **cp.get() returns data directly** — NOT wrapped in `{"success": true, "data": ...}`
- **cp.get_appdata('field_name')** — ALWAYS pass a field name. Without args returns a LIST, not a dict
- **cp.put_appdata(name, value)** — TWO separate string arguments, NOT a dict
- Appdata stored at `config/system/sdk/appdata`

### Key Helpers

```python
cp.log(msg)                          # Log (syslog on router, stdout local)
cp.get('status/path')                # Read status/config tree
cp.put('config/path', value)         # Write config/control
cp.post('config/path/', value)       # Create new entries
cp.delete('config/path/id')          # Delete entries
cp.get_appdata('field')              # Read app config field
cp.put_appdata('name', 'value')      # Write app config
cp.wait_for_wan_connection()         # Block until WAN up
cp.speed_test(interface, duration, direction)  # Netperf speed test
cp.get_wan_profiles()                # WAN rules sorted by priority
cp.get_sims()                        # List of modem UID strings
cp.register('put', 'control/path', callback)  # Event callback (on-router only)
```

---

## NCOS API Reference

Full docs at `docs/ncos-api/`. Key paths:

### Status (read-only)
- `status/wan/connection_state` → `'connected'` or `'disconnected'`
- `status/wan/devices` → dict keyed by device name, each has `info`, `status`, `diagnostics`
- `status/wan/primary_device` → device name string
- `status/system` → cpu (fractions, not %), memory (bytes), uptime (seconds), temperature (°C)
- `status/lan/clients` → list of `{ip_address, mac, hostname}` — NO bandwidth data here
- `status/client_usage` → `{enabled, stats: [{mac, ip, up_bytes, down_bytes, ...}]}`
- `status/gps/nmea` → array of NMEA sentence strings
- `status/firewall` → conntrack entries, state_entry_count
- `status/mount` → `{disk_usage: {total_bytes, free_bytes}}`

### Config (persistent settings)
- `config/wan/rules2` → WAN profiles (list of dicts with `_id_`, trigger_string, priority, disabled)
- `config/qos` → `{enabled, queues, rules}` — MUST put entire object, NO MAC support in rules
- `config/security/zfw/filter_policies` → firewall policies (must put entire rules array)
- `config/system/system_id` → router hostname
- `config/lan` → LAN network config array

### Control (actions)
- `control/system/reboot` → PUT 1 to reboot
- `control/gpio/LED_SS_0` → PUT 0/1
- `control/ping/start` → PUT `{host, num}`
- `control/netperf` → speed test (see docs/ncos-api/control/)

### REST API format
- REST returns wrapped: `{"success": true, "data": ...}`
- REST writes use form-encoded `data=` parameter, NOT JSON body
- `curl -k -u admin:pass -X PUT "https://ROUTER/api/config/path" -d 'data={"key":"val"}'`

### DTD (schema verification)
```bash
curl -s -u admin:pass http://router/api/dtd/config/path | python3 -m json.tool
```

---

## Key Gotchas

- `status/lan/clients` has NO rx_bytes/tx_bytes — use `status/client_usage`
- QoS rules do NOT support MAC addresses — only IP via lipaddr/lmask
- Firewall conntrack: track by `id` field to avoid counting stale connections
- ARP dump interface names have trailing digits — strip before lookup
- Firewall filter policies require full rules array put
- Cert creation is async — wait ~5 seconds after `cp.put('control/certmgmt/ca', {...})`
- `cp.register` callback receives 3 args: `(path, value, args)` — do NOT use `*args`
- `cp.register()` for control tree MUST use `'put'` (lowercase) — `'set'`/`'PUT'` silently fails
- Do NOT `cp.put()` before `cp.register()` — causes socket desync
- Control tree keys persist across redeploys — keep path names stable
- REST API returns masked `$0$` password hashes — only SDK socket returns real `$3$` hashes
- SCP remote path MUST be `/app_upload` (no trailing slash)
- `requests` is pre-installed on cppython — do NOT bundle it
- Signal diagnostics use UPPERCASE keys: `DBM`, `RSRP`, `SINR`, `CARRID`, `RAD_IF`

---

## Web Development

- ALWAYS use Python's built-in `http.server` — never Flask, Bottle, etc.
- Default port: 8000
- ALWAYS set `SO_REUSEADDR` before binding
- Run HTTPServer in a daemon thread: `Thread(target=server.serve_forever, daemon=True).start()`
- Vanilla JavaScript (ES6+ fine), semantic HTML5, CSS Grid/Flexbox
- Serve all assets locally — no external CDNs
- For LAN client access: firewall must allow Primary LAN Zone → Router Zone forwarding
- NEVER pass parameters in onclick attributes — use data attributes

---

## Third-Party Libraries

- Install to app folder: `.venv/bin/pip install -t path/to/app_folder library_name`
- Only pure Python (.py) — no .pyc, .so, .pyd
- Must work on Python 3.8
- `requests` already on router — don't bundle
- `redis` not available — make conditional
- cppython missing: `pkg_resources`, `decimal`, `csv`
- cppython has: `threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`, `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`, `time`, `xml.etree.ElementTree`

---

## Speedtest

- NO Ookla license for SDK apps — never bundle/distribute
- Engine priority: Ookla (BYOB) → Netperf (built-in) → iPerf3 (user server)
- Default: `cp.speed_test(interface='rmnet501', duration=10, direction='both')`
- Netperf CANNOT run concurrent tests — test modems sequentially
- Ookla/iPerf3 CAN run concurrent with source IP binding

---

## GPS and NMEA

- Use `pynmeagps` for parsing — never write custom parsers
- Install fresh via pip, never copy from another app
- `$PCPTMINR` is proprietary Cradlepoint — catch "Unknown msgID" and skip
- Speed from knots: `speed_kmh = msg.spd * 1.852`

---

## Docker / Containers

- Deploy via REST: POST to `/api/config/container/projects/`
- Use Compose version `"2.4"` (not v3)
- Named volumes MUST have `driver: local`
- Use `restart: unless-stopped` (not `always`)
- NO `network_mode: host` — use `ports:` instead
- NO memory limits (not supported)
- Use alpine-based images

---

## Project Structure

```
apps/{app_name}/
├── package.ini          # Metadata (uuid, version, vendor, tags)
├── cp.py                # CP module (auto-generated, never modify)
├── {app_name}.py        # Main logic
├── start.sh             # Uses cppython (never modify)
├── readme.md            # Usage and appdata fields
└── METADATA/            # Build signatures (auto-generated)
```

---

## Build & Deploy

```bash
# Setup
python3 make.py setup

# Create new app
.venv/bin/python3 make.py create {app_name}

# Deploy (purge → build → install → show logs)
.venv/bin/python3 make.py deploy {app_name}

# Other commands
.venv/bin/python3 make.py status {app_name}
.venv/bin/python3 make.py stop {app_name}
.venv/bin/python3 make.py uninstall {app_name}
```

- If no app_name given, uses `app_name` from `sdk_settings.ini`
- NEVER use `make.py install` directly — always use `deploy`
- NEVER overwrite `package.ini`, `start.sh`, or `cp.py` after creation

---

## API Verification Workflow

Before writing code that uses an API path:

1. Search docs: `grep -r "keyword" docs/ncos-api/ --include="*.md"`
2. Check DTD: `curl -s -u admin:pass http://router/api/dtd/config/path`
3. Test with curl: `curl -s -u admin:pass http://router/api/status/path`
4. Only use fields that actually exist in the response
5. Then write code

---

## Error Handling

Always wrap API calls:

```python
try:
    data = cp.get('status/system')
    if data:
        # process
except Exception as e:
    cp.log(f"Error: {e}")
```

---

## Local Development

- Run locally: `.venv/bin/python3 my_app/my_app.py`
- cp.get/put/post/delete work via REST to dev router
- cp.log() prints to stdout
- cp.register(), cp.alert(), cp.decrypt() do NOT work locally
- Web servers bind to YOUR machine, not the router
