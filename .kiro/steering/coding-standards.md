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

## SDK Developer Guide

- **Full SDK development docs**: `docs/NCOS_SDK_Developer_Guide.md` — covers SDK concepts, app lifecycle, packaging, and development practices

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
- **IMPORTANT: ALWAYS deploy after creating or modifying an app.** Run `.venv\Scripts\python make.py deploy {app_name}` (Windows) or `.venv/bin/python3 make.py deploy {app_name}` (Mac/Linux) immediately after code changes. Do not ask — just deploy. See `workflow.md` for full details.


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
