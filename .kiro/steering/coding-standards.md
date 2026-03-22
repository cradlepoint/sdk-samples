---
inclusion: auto
description: "Python 3.8 coding standards for Cradlepoint SDK apps"
---
# Cradlepoint SDK Coding Standards

Applications run on Cradlepoint routers using Python 3.8.

## Python 3.8 Constraints

- **NEVER use bitwise OR (|) for types** - Python 3.8 doesn't support `str | None` syntax
- **NEVER use arrow functions (=>) in JavaScript** - Python 3.8 environment doesn't support ES6, use ES5 `function(){}` syntax
- **NEVER use template literals in JavaScript** - use string concatenation instead: `'text' + var + 'more'`
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
- **Boot logging** - `cp.log('Starting...')` ASAP at startup
- **Wait for connectivity** - use `cp.wait_for_wan_connection()` if internet is needed
- **NEVER modify packaged files** - Apps have digital signatures (MANIFEST.json). Router deletes app if any packaged file is modified. Write to NEW files only (e.g., `data.csv`, `logs/output.txt`)
- **Persist application state** - Save state to survive reboots. Use a state file for runtime state, or appdata for user-configurable values
- **NEVER write default values to appdata** - Writing defaults to appdata overrides group configs pushed from NCM. Instead, read appdata and use a default in code if the field is missing/empty. For required fields with no sensible default, log a warning and skip that feature
- **Router architecture is ARM64 (aarch64) with musl libc** - when downloading binaries, use aarch64/arm64 versions, NOT x86_64

## Local Development (Running on Your Computer)

- **Apps can run locally** - `python3 my_app/my_app.py` runs the app on your computer. cp.py auto-detects it's not on a router and uses HTTP REST to communicate with the dev router specified in `sdk_settings.ini`
- **cp.get/put/post/delete work locally** - all API calls route through REST to the dev router
- **cp.log() prints to stdout locally** - output goes to your terminal instead of syslog
- **cp.alert() does NOT work locally** - logs the alert text to console but does not send to NCM
- **cp.register()/cp.unregister() do NOT work locally** - event callbacks require the router's internal socket, no REST equivalent exists
- **cp.decrypt() does NOT work locally** - returns None and logs a message
- **Web servers bind to YOUR machine locally** - if your app runs an HTTP server, it binds to your computer's port, not the router's. LAN clients on the router cannot reach it
- **Serial/GPIO not available locally** - these access your computer's hardware, not the router's
- **Use local execution for fast iteration** - test API reads, data processing, and business logic locally, then deploy to router for final testing of alerts, events, web UIs, serial, and GPIO

## Python Libraries and Dependencies

- **Install libraries directly to app folder**: `pip3 install -t path/to/app_folder library_name`
- **Example**: `pip3 install -t gpio_modem_control requests`
- **CRITICAL: No .pyc or .so files** - routers only support pure Python (.py) files
- Libraries are packaged with the app and deployed to the router
- Keep dependencies minimal - routers have limited storage
- Test that libraries work on Python 3.8
- **cppython is missing stdlib modules** - `pkg_resources`, `decimal`, `csv` are not available. Copy shims from existing apps (e.g., `decimal.py`, `csv.py`, `_csv.py` from 5GSpeed or Mobile_Site_Survey)
- **cppython HAS these stdlib modules** - `threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`, `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`, `time`, `xml.etree.ElementTree` — all work as expected
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

## Speedtest Implementation

- **ALWAYS use production wrapper from 5GSpeed** - Copy `speedtest_ookla.py` and `ookla` binary from @5GSpeed
- **Import**: `from speedtest_ookla import Speedtest`
- **Usage**: `s = Speedtest(timeout=90); s.start(); results = s.results`
- **Results**: `results.download` (bps), `results.upload` (bps), `results.ping` (ms), `results.server`, `results.isp`
- **Features**: Real-time monitoring, retry logic, partial results, interface binding, timeout handling
- **Multi-modem testing**: Use Mobile_Site_Survey's `speedtest.py` wrapper for simultaneous tests across multiple modems with source routing
- **NEVER write custom speedtest code** - always use existing wrappers

## Web Development

- **Default port: 8000** - use port 8000 for web applications unless there's a conflict
- **ALWAYS set SO_REUSEADDR** before binding: `server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)`
- **Port conflicts on redeployment** - SO_REUSEADDR doesn't prevent "Address in use" errors when redeploying without router reboot. If port 8000 is in use, either reboot router or use a different port (8001, 8002, etc.)
- **Background web server pattern** - run `http.server.HTTPServer` in a daemon thread: `Thread(target=server.serve_forever, daemon=True).start()`. Main thread runs the app's primary loop
- **Dashboard auto-refresh with server-side timestamps** - compute `_ago` values (seconds since event) on the server, not the client. Client clocks may differ from router. Return `connected_ago`, `last_rx_ago` etc. as integers
- **Dynamic download filenames** - use router hostname and timestamp: `cp.get('config/system/system_id')` + `datetime.now().strftime('%Y%m%d_%H%M%S')`
- **Light/dark mode** - use `data-theme` attribute on `<html>` element, persist with `localStorage.setItem('theme', 'light'|'dark')`, load on page init
- **ALWAYS use ES5 JavaScript syntax** - NO arrow functions `=>`, NO template literals - Python 3.8 environment doesn't support ES6
- **Use `function(){}` instead of `()=>{}`** for all functions
- **Use string concatenation `'text'+var+'more'` instead of template literals**
- **NEVER pass parameters in onclick attributes** - Use HTML entities (&quot;) or data attributes instead
- **For onclick with params**: Use `onclick="func(&quot;param1&quot;,&quot;param2&quot;)"` with &quot; entities, NOT escaped quotes
- **Auto-refresh dashboards must preserve user input** - Save `document.activeElement.id` and `.value`, restore after innerHTML update
- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- CSS variables for theming, mobile-first responsive
- Use @web_app_template as style reference
- Proper error handling with try/catch
- Serve assets locally (no external dependencies)
- Implement signal handlers for graceful shutdown
- Log which port server started on
