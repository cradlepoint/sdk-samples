---
inclusion: auto
description: "Python 3.8 coding standards for Cradlepoint SDK apps"
---
# Cradlepoint SDK Coding Standards

Applications run on Cradlepoint routers using Python 3.8.

## Python 3.8 Constraints

- **NEVER use bitwise OR (|) for types** - Python 3.8 doesn't support `str | None` syntax
- **NEVER pass parameters in onclick attributes** - quote escaping is error-prone, use data attributes and `this` instead
- **ALWAYS use try/except** - never raise exceptions, catch and log them
- **NEVER use random or generated data** - only use real data from router APIs, sensors, or external sources; if data is unavailable, use None or empty values
- Use 4 spaces, follow PEP 8, keep lines under 100 chars
- Never use bare `except:` clauses

## Router Environment

- **No screen** - use `cp.log()` for all output (never print())
- **No keyboard** - never use `input()` or `KeyboardInterrupt`
- **Relative paths only** - use `tmp/`, never absolute like `/tmp`
- **Create directories before writing** - use `os.makedirs('tmp', exist_ok=True)` before writing to tmp/
- **Python is "cppython"** - start.sh must use `cppython`
- **Static apps** - no .pyc or .so files, but statically linked ARM64 binaries ARE supported
- **Bundled binaries lose execute permission** - tar extraction on the router does NOT preserve the execute bit. Always `os.chmod('binary', 0o755)` before first use. Check with `os.path.exists()` not `os.access(path, os.X_OK)`
- **Boot logging** - `cp.log('Starting...')` ASAP at startup
- **Wait for connectivity** - use `cp.wait_for_wan_connection()` if internet is needed
- **NEVER modify packaged files** - Apps have digital signatures (MANIFEST.json). Router deletes app if any packaged file is modified. Write to NEW files only (e.g., `data.csv`, `logs/output.txt`)
- **Persist application state** - Save state to survive reboots. Use a state file for runtime state, or appdata for user-configurable values
- **NEVER write default values to appdata** - Writing defaults to appdata overrides group configs pushed from NCM. Instead, read appdata and use a default in code if the field is missing/empty. For required fields with no sensible default, log a warning and skip that feature
- **Router architecture is ARM64 (aarch64) with musl libc** - when downloading binaries, use aarch64/arm64 versions, NOT x86_64

## Local Development (Running on Your Computer)

- **Apps can run locally** - `.venv/bin/python3 my_app/my_app.py` (Mac/Linux) or `.venv\Scripts\python my_app/my_app.py` (Windows) runs the app on your computer. cp.py auto-detects it's not on a router and uses HTTP REST to communicate with the dev router specified in `sdk_settings.ini`
- **cp.get/put/post/delete work locally** - all API calls route through REST to the dev router
- **cp.log() prints to stdout locally** - output goes to your terminal instead of syslog
- **cp.alert() does NOT work locally** - logs the alert text to console but does not send to NCM
- **cp.register()/cp.unregister() do NOT work locally** - event callbacks require the router's internal socket, no REST equivalent exists
- **cp.decrypt() does NOT work locally** - returns None and logs a message
- **Web servers bind to YOUR machine locally** - if your app runs an HTTP server, it binds to your computer's port, not the router's. LAN clients on the router cannot reach it
- **Serial/GPIO not available locally** - these access your computer's hardware, not the router's
- **Use local execution for fast iteration** - test API reads, data processing, and business logic locally, then deploy to router for final testing of alerts, events, web UIs, serial, and GPIO

## Python Libraries and Dependencies

- **Install libraries directly to app folder**: `.venv/bin/pip3 install -t path/to/app_folder library_name` (Mac/Linux) or `.venv\Scripts\pip install -t path/to/app_folder library_name` (Windows)
- **Example**: `.venv/bin/pip3 install -t gpio_modem_control requests` (Mac/Linux) or `.venv\Scripts\pip install -t gpio_modem_control requests` (Windows)
- **CRITICAL: No .pyc or .so files** - routers only support pure Python (.py) files
- Libraries are packaged with the app and deployed to the router
- Keep dependencies minimal - routers have limited storage
- Test that libraries work on Python 3.8
- **cppython is missing stdlib modules** - `pkg_resources`, `decimal`, `csv` are not available. Copy shims from existing apps (e.g., `decimal.py`, `csv.py`, `_csv.py` from 5GSpeed or Mobile_Site_Survey)
- **CAVEAT: `_csv.py` shim is stub-only** - the `_csv.py` file from 5GSpeed/Mobile_Site_Survey has all functions as `pass` (return None). It only works on actual cppython where the real C `_csv` module takes precedence. `csv.writer()` and `csv.reader()` return None when the C module isn't loaded. **For simple CSV writing, use plain string concatenation** (`','.join(fields) + '\n'`) instead of `csv.writer`. Only use the csv shim if you need `DictReader`/`DictWriter` and are deploying to a real router
- **cppython HAS these stdlib modules** - `threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`, `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`, `time`, `xml.etree.ElementTree` — all work as expected
- **`requests` is available system-wide on cppython** - do NOT bundle it in the app folder (pip install -t). Just `import requests` — it's pre-installed on the router. Bundling a local copy will shadow the system version and likely fail due to Python 3.8 incompatibility with newer urllib3
- **`redis` is NOT available** - if a library depends on redis, make it conditional with try/except ImportError
- **C-accelerated stdlib types cannot be monkey-patched** - `xml.etree.ElementTree.Element` is a C type on cppython. Cannot add methods or subclass it. If a library uses lxml-specific methods like `iterchildren()` or `clear(keep_tail=True)`, patch the library source directly
- **lxml can be replaced with a pure Python shim** - `xml.etree.ElementTree` covers most lxml.etree usage. Key differences to patch in library source:
  - Replace `elm.iterchildren()` with `iter(elm)` or `list(elm)`
  - Replace `elm.clear(keep_tail=True)` with `tail=elm.tail; elm.clear(); elm.tail=tail`
  - `etree.tostring()`: use `ET.tostring(elm, encoding='unicode').encode('utf-8')` to avoid unwanted `<?xml?>` declarations (lxml omits them by default, stdlib adds them with byte encodings). NEVER use `encoding='utf-8'` directly — it returns bytes WITH xml declaration
  - `etree.XMLSyntaxError` → `xml.etree.ElementTree.ParseError`
  - `etree.XMLPullParser` works on cppython — use for streaming XML parsing
  - `etree.Element` is a C type — cannot add attributes/methods at runtime, cannot subclass
- **Libraries using `pkg_resources` for versioning** - hardcode the version string directly in `__init__.py` instead

## Docker / Container Development

- **Deploy containers via REST API** - POST to `/api/config/container/projects/` with JSON body. Do NOT use SSH/SCP (router SSH is a restricted CLI, not bash)
- **Container project schema** (`config/container/projects`):
  - `name` (string) — project name
  - `config` (string) — docker-compose YAML as a single escaped string
  - `enabled` (boolean) — whether the project is active
  - `update_interval` (integer) — update check interval (0 = disabled)
- **Named volumes MUST have `driver: local`** - Cradlepoint's container runtime requires explicit `driver: local` on all named volumes in docker-compose files. Without it, volume creation fails
- **Use alpine-based images** - prefer `-alpine` image variants to reduce size and RAM usage on the router's limited resources
- **Expect ~200-300MB RAM for InfluxDB** - monitor system metrics when running databases in containers alongside SDK apps
- **SSH `container` CLI** - can list, start, stop, pull, exec, and view logs. `container exec` does NOT return stdout to the SSH session
- **Container status API** - `status/container/{name}` shows state, info, and stats per container
- **NO memory limits in docker-compose** - Cradlepoint's container runtime does not support `mem_limit`, `deploy.resources.limits.memory`, or any memory constraint options. Omit them entirely or the compose validation will fail
- **Use Compose version "2.4"** - Cradlepoint's container runtime uses Compose v2.4, not v3. Always set `version: "2.4"` in docker-compose files
- **Use `restart: unless-stopped`** - Cradlepoint does not allow `restart: always`. Use `unless-stopped` instead
- **NO `network_mode: host`** - Cradlepoint's container runtime only supports bridged networking. Use `ports:` to publish ports instead of `network_mode: host`
- **Set shared memory with `shm_size`** - some services (e.g. databases, browsers) need more than the default 64MB `/dev/shm`. Set `shm_size: '1gb'` (or appropriate size) at the service level in docker-compose

Example deploy via curl:
```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/projects/" \
  -H "Content-Type: application/json" \
  -d '{"name":"myproject","config":"version: \"2.4\"\nservices:\n  ...","enabled":true,"update_interval":0}'
```

Example volume declaration:
```yaml
volumes:
  my-data:
    driver: local
```

## Error Handling

Always wrap API calls in try/except and log errors:

```python
try:
    data = cp.get('status/system')
    if data:
        # process data
except Exception as e:
    cp.log(f"Error getting system status: {e}")
```

## GPS and NMEA Sentence Parsing

- **Use `pynmeagps` for NMEA parsing** - never write custom NMEA parsers. Install to app folder: `.venv/bin/pip3 install -t path/to/app_folder pynmeagps` (Mac/Linux) or `.venv\Scripts\pip install -t path/to/app_folder pynmeagps` (Windows)
- **NEVER copy pynmeagps from another app** - always use pip to install a fresh copy into the target app folder. This ensures you get the latest compatible version
- **NMEA data sources on the router**:
  - `status/gps/nmea` — array of current NMEA sentences
  - `status/gps/devices/{mdm_uid}/current_nmea` — per-modem NMEA sentences
  - IBR1700 GNSS daemon — TCP socket on `127.0.0.1:17488` (see `ibr1700_gnss` app)
- **NEVER manually split NMEA sentences by comma** - use pynmeagps for proper checksum validation and typed field access
- **`PCPTMINR` is a proprietary Cradlepoint NMEA sentence** - it appears in `status/gps/nmea` and pynmeagps will raise "Unknown msgID". This is expected — catch the exception and skip it silently
- **RTK NMEA source**: `status/rtk/ntrip/rtk_sentence` returns a single GNGGA string (NOT an array like `status/gps/nmea`). It provides RTK-corrected position data. Wrap in a list before parsing: `[rtk_sentence]`. The RTK status object also has `rtk_quality`, `connected`, `last_gga_reminder`, and RTCM stats
- **Talker IDs**: `GP` = GPS only, `GN` = multi-constellation (GPS+GLONASS+etc.), `GL` = GLONASS. Cradlepoint routers may emit either `GPRMC` or `GNRMC` depending on modem/config. pynmeagps handles both transparently — `msg.msgID` returns `RMC` regardless of talker prefix
- **Common sentence types and their pynmeagps fields**:
  - **GGA** (fix quality, position, altitude): `msg.lat`, `msg.lon`, `msg.alt` (meters above sea level), `msg.altUnit` (`'M'`), `msg.numSV` (satellite count), `msg.quality` (0=no fix, 1=GPS, 2=DGPS), `msg.HDOP`, `msg.sep` (geoid separation)
  - **RMC** (position, speed, course, date/time): `msg.lat`, `msg.lon`, `msg.spd` (speed over ground in knots), `msg.cog` (course over ground in degrees true), `msg.date`, `msg.time`, `msg.status` (`'A'`=active/valid, `'V'`=void)
  - **VTG** (track/speed detail): `msg.cogt` (true course°), `msg.cogm` (magnetic course°), `msg.sogn` (speed knots), `msg.sogk` (speed km/h)
  - **GSA** (DOP and active satellites): `msg.PDOP`, `msg.HDOP`, `msg.VDOP`, `msg.navMode` (1=no fix, 2=2D, 3=3D)
  - **GSV** (satellites in view): `msg.numSV`, repeating group with `svid`, `elv`, `az`, `cno`
- **Speed conversion from knots**: `speed_kmh = msg.spd * 1.852` or `speed_mph = msg.spd * 1.15078`
- **Parsing example with position, altitude, speed, and heading**:
```python
from pynmeagps import NMEAReader
import cp

nmea_sentences = cp.get('status/gps/nmea')
if nmea_sentences:
    for sentence in nmea_sentences:
        try:
            msg = NMEAReader.parse(sentence)
            if msg.msgID == 'GGA':
                cp.log(f'GGA: lat={msg.lat} lon={msg.lon} '
                       f'alt={msg.alt}m sats={msg.numSV}')
            elif msg.msgID == 'RMC':
                if msg.status == 'A':
                    cp.log(f'RMC: lat={msg.lat} lon={msg.lon} '
                           f'speed={msg.spd}kn course={msg.cog}°')
        except Exception as e:
            cp.log(f'NMEA parse error: {e}')
```

## Speedtest Implementation

- **NO Ookla license exists for SDK apps** - do NOT bundle or distribute the Ookla binary. All apps must work without it.
- **Engine priority**: Ookla (BYOB) → Netperf (built-in) → iPerf3 (user-provided server)
- **BYOB (Bring Your Own Binary)**: If a customer has their own Ookla license, they can drop the `ookla` binary into the app folder. Apps should detect it and use it automatically — but NEVER require it.
- **Default engine is Netperf** - uses `cp.speed_test()` from cp.py. No binary needed, no server config needed, supports per-interface testing via `ifc_wan`.
- **iPerf3 for user-controlled servers** - use when the user needs to test against their own infrastructure. Requires a server address (appdata or UI input). Bundle `iperf3-arm64v8` binary from @speedtest_web.

### Engine detection pattern (use in all speedtest apps):
```python
import os

OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')

def _find_binary(candidates):
    """Find first existing binary from candidates list, chmod if needed."""
    for name in candidates:
        if os.path.exists(name):
            if not os.access(name, os.X_OK):
                try:
                    os.chmod(name, 0o755)
                except Exception:
                    pass
            return name
    return None

def has_ookla():
    return _find_binary(OOKLA_BINARIES) is not None

def has_iperf3():
    return _find_binary(IPERF3_BINARIES) is not None
```

### Simple speedtest (single interface, no UI):
```python
def run_speedtest():
    """Ookla if present, else netperf."""
    if has_ookla():
        result = run_ookla()
        if result:
            return result
        cp.log('Ookla failed, falling back to netperf...')
    return run_netperf()

def run_ookla():
    try:
        from speedtest_ookla import Speedtest
        s = Speedtest(timeout=90)
        s.start()
        return s.results.download / 1e6, s.results.upload / 1e6
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None

def run_netperf():
    result = cp.speed_test(duration=10, direction='both')
    if result:
        return result['download_bps'] / 1e6, result['upload_bps'] / 1e6
    return 0.0, 0.0
```

### Per-interface testing (multi-SIM apps):
- **Netperf**: Use `cp.speed_test(interface=iface)` — the `ifc_wan` parameter handles routing natively. No source routing needed.
- **Ookla**: Requires source routing or `-i source_ip` binding (see Mobile_Site_Survey `speedtest.py`)
- **iPerf3**: Use `-B source_ip` for binding. Needs port range for concurrent tests (one port per modem).

### Concurrent multi-modem testing:
- **Netperf CANNOT run concurrent tests** - it's a single shared router resource. Test modems sequentially.
- **Ookla CAN run concurrent tests** - each is an independent subprocess with `-i source_ip`
- **iPerf3 CAN run concurrent tests** - each subprocess uses `-B source_ip` and a different port from a configured range (e.g. `5201-5210`)
- **For concurrent multi-modem**: Use Mobile_Site_Survey's `speedtest.py` wrapper which handles both Ookla (BYOB) and iPerf3 with port allocation

### Netperf API (cp.speed_test):
```python
result = cp.speed_test(
    interface='rmnet501',  # ifc_wan - routes test through this interface
    duration=10,           # seconds
    direction='both'       # 'recv', 'send', or 'both'
)
# Returns: {'download_bps': float, 'upload_bps': float, ...}
```

### Netperf TCP RR (latency/jitter):
Use `control/netperf` with `"rr": True` for latency measurement. See @speedtest_web for implementation.

### iPerf3 pattern:
```python
cmd = ['./iperf3-arm64v8', '-c', server, '-p', str(port), '-t', '10', '-J']
cmd.append('-R')  # reverse for download
# For source binding: cmd.extend(['-B', source_ip])  # MUST be IP address, NOT interface name
```
- **`-B` requires an IP address** — passing an interface name (e.g. `pmip3`) causes "Invalid argument". Resolve iface to IP first via `status/wan/devices/{uid}/status/ipinfo/ip_address`

### Reference apps:
- **@speedtest_web** - Full web UI with all 3 engines, history, reports, latency/jitter
- **@5GSpeed** - Simple Ookla→netperf fallback pattern
- **@Mobile_Site_Survey** - Concurrent multi-modem with Ookla BYOB + iPerf3 port range

## Web Development

- **ALWAYS use Python's built-in `http.server` module** - never use third-party web frameworks (Flask, Bottle, CherryPy, etc.). The native `http.server.HTTPServer` is available on cppython and has zero dependencies
- **LAN client access to router ports requires firewall zone forwarding** - For a client device on the LAN to reach a port on the router (SDK app web UI, SNMP agent, container-published port, etc.), the firewall must have a forwarding rule from the Primary LAN Zone to the Router Zone. If an app is running but LAN clients get connection timeouts, the zone forwarding is the first thing to check. This is configured at `config/firewall/zone_fwd` or via the NCOS UI under Security > Zone Firewall.
- **NCM API does NOT support CORS** - the NetCloud Manager API at `us0.cradlepointecm.com` blocks cross-origin browser requests (no `Access-Control-Allow-Origin` header). Browser JS from third-party origins (e.g., GitHub Pages) cannot call NCM APIs directly. Use server-side calls (curl, Python requests) or the NCM web UI for uploads
- **Default port: 8000** - use port 8000 for web applications unless there's a conflict
- **ALWAYS set SO_REUSEADDR** before binding: `server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)`
- **Port conflicts on redeployment** - SO_REUSEADDR doesn't prevent "Address in use" errors when redeploying without router reboot. If port 8000 is in use, either reboot router or use a different port (8001, 8002, etc.)
- **Background web server pattern** - run `http.server.HTTPServer` in a daemon thread: `Thread(target=server.serve_forever, daemon=True).start()`. Main thread runs the app's primary loop
- **Dashboard auto-refresh with server-side timestamps** - compute `_ago` values (seconds since event) on the server, not the client. Client clocks may differ from router. Return `connected_ago`, `last_rx_ago` etc. as integers
- **Dynamic download filenames** - use router hostname and timestamp: `cp.get('config/system/system_id')` + `datetime.now().strftime('%Y%m%d_%H%M%S')`
- **Light/dark mode** - use `data-theme` attribute on `<html>` element, persist with `localStorage.setItem('theme', 'light'|'dark')`, load on page init
- **ES6+ JavaScript is fine** - arrow functions, template literals, const/let, async/await, destructuring all work in modern browsers that access the router UI
- **NEVER pass parameters in onclick attributes** - Use HTML entities (&quot;) or data attributes instead
- **For onclick with params**: Use `onclick="func(&quot;param1&quot;,&quot;param2&quot;)"` with &quot; entities, NOT escaped quotes
- **Auto-refresh dashboards must preserve user input** - Save `document.activeElement.id` and `.value`, restore after innerHTML update
- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- CSS variables for theming, mobile-first responsive
- **ALWAYS copy `static/` folder from @web_app_template into new web apps** - this includes `css/style.css`, `js/script.js`, `libs/font-awesome.min.css`, `libs/jquery-3.5.1.min.js`, and `libs/webfonts/`. These are required for the design system to work
- **ALWAYS use `your_web_app.html` from @web_app_template as the starting HTML** - copy it as `index.html` into your app, then modify the title, sidebar nav, and content sections. NEVER write HTML from scratch
- **NEVER write custom CSS or include external stylesheets** - the template's `style.css` provides the complete design system (layout, colors, dark mode, components). Add app-specific styles in a `<style>` block or a separate file that supplements (not replaces) the template CSS
- Proper error handling with try/catch
- Serve assets locally (no external dependencies)
- Implement signal handlers for graceful shutdown
- Log which port server started on
