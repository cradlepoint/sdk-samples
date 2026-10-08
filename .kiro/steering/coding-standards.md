# Cradlepoint SDK Coding Standards

The hard guardrails are in `core.md` (always loaded). This file is the detail behind them.

## Python 3.8 / cppython

- No `str | None` — use `Optional[str]` from `typing`. No `match`/`case`. Avoid the walrus
  operator in complex expressions.
- 4 spaces, PEP 8, lines under 100 chars. Never a bare `except:` — catch `Exception`.
- **Full SDK development docs**: `docs/NCOS_SDK_Developer_Guide.md` — SDK concepts, app
  lifecycle, packaging, development practices.

## App Lifecycle on the Router

- **`start.sh` must invoke `cppython`** — that is the router's Python 3.8 interpreter.
- **Log at boot** — `cp.log('Starting...')` as early as possible.
- **Wait for connectivity** — `cp.wait_for_wan_connection()` if the app needs the internet.
- **Persist application state** — save state so it survives reboots. Use a state file for runtime
  state, or appdata for user-configurable values.
- **`restart = true` in `package.ini` means the router RELAUNCHES the app whenever the process
  exits** — a "run once then exit" app becomes a hot restart loop (observed relaunching every
  ~2 seconds). This is dangerous for apps with external side effects: a provisioning app that
  creates a cloud resource per run will hammer that API. One-shot apps must **never fall off the
  end of `main()`** — finish the work, then park in a `while True: time.sleep(...)` loop
  (optionally logging status), and do the same on unrecoverable errors so a failure idles instead
  of spinning. Pair this with a state file so a genuine restart or reboot skips work already done.

## Bundled Binaries

- **Static apps** — no `.pyc` or `.so` files, but statically linked ARM64 binaries ARE supported.
- **Bundled binaries lose the execute bit** — tar extraction on the router does not preserve it.
  Always `os.chmod('binary', 0o755)` before first use. Check with `os.path.exists()`, not
  `os.access(path, os.X_OK)`.
- Router architecture is **ARM64 (aarch64) with musl libc** — download aarch64/arm64 builds,
  never x86_64.

## Memory Management

Routers have limited RAM. Fetching or holding large objects in a polling loop causes peak-memory
spikes and fragmentation that add up over long unattended uptimes.

- **NEVER fetch large API trees in a polling loop** — use the most specific sub-path possible.
  Use `cp.get('status/vpn/tunnels')` NOT `cp.get('status/vpn')`, which returns massive
  config/policy text blobs. Same for `status/wan/devices/{id}/diagnostics` vs `status/wan/devices`
  (all devices). This also avoids re-parsing a big blob into hundreds of Python objects every poll.
- **Don't accumulate data in global collections without bounds** — clean up entries for items that
  no longer exist, and cap collection sizes where unbounded growth is possible.
- **Prefer simple types over nested structures** — store a string ID or a boolean flag rather than
  caching entire API response dicts.
- **Don't hold previous poll results longer than needed** — if a variable holding a big response
  outlives the loop iteration (stored on `self` or in a global), drop the reference when done.
  Reassigning a local each iteration already frees the old value; no explicit `del` needed.
- **Match poll interval to response size** — single values or short lists: 1–2 s. Device status
  objects: 3–5 s. Large trees (full WAN/VPN status): 10–30 s, or use `cp.register()` instead.
- **ALWAYS `time.sleep()` in polling loops** — a bare `while True` burns CPU and accelerates
  object allocation for no benefit.
- **Monitor `status/system/memory` for complex apps** — log available memory at startup and
  periodically. A steady decline over hours indicates a leak. If the app is OOM-killed it vanishes
  from `status/system/sdk` with no log entry. Simple fixed-workload apps don't need this.
- **Consider a memory guard based on app complexity** — NOT every app needs one. Skip it for
  simple apps with fixed-size workloads (polling a few small paths on a timer, no growing
  collections). DO include it when the app processes variable-size data (client lists, VPN
  tunnels, log buffers), accumulates state over time, or runs unattended on fleet-deployed
  routers. The guard checks `memavailable` every 30–60 s: at ~20% available, log a warning and
  shed load (clear caches, back off poll frequency); at ~10%, `cp.alert()` to NCM and
  `sys.exit(0)` to self-restart. Tune thresholds per app. The router restarts apps with
  `auto_start=true`, reclaiming all leaked memory — better than letting the OOM killer choose.

## Python Libraries and Dependencies

- **Install into the app folder**: `.venv/bin/pip3 install -t path/to/app_folder library_name`
  (Mac/Linux) or `.venv\Scripts\pip install -t path/to/app_folder library_name` (Windows).
  Libraries are packaged with the app and deployed to the router. Keep them minimal — routers
  have limited storage — and confirm they work on Python 3.8.
- **No `.pyc` or `.so`** — routers only support pure Python.
- **`requests` is available system-wide on cppython** — do NOT bundle it. Just `import requests`.
  A bundled copy shadows the system version and will likely fail on Python 3.8 because of newer
  urllib3.
- **`redis` is NOT available** — make any dependency on it conditional with `try/except ImportError`.
- **cppython is MISSING `pkg_resources`, `decimal`, and `csv`** — copy shims from an existing app
  (`decimal.py`, `csv.py`, `_csv.py` from 5GSpeed or Mobile_Site_Survey).
  - **CAVEAT: the `_csv.py` shim is stub-only** — every function is `pass` (returns None). It only
    works on real cppython, where the C `_csv` module takes precedence; off-router,
    `csv.writer()`/`csv.reader()` return None. **For simple CSV writing use plain string
    concatenation** (`','.join(fields) + '\n'`). Only use the shim if you need
    `DictReader`/`DictWriter` and are deploying to a real router.
  - Libraries that use `pkg_resources` for versioning — hardcode the version string in
    `__init__.py`.
- **cppython HAS** `threading`, `select`, `ssl`, `http.server`, `socket`, `configparser`,
  `zipfile`, `io`, `hashlib`, `hmac`, `base64`, `struct`, `uuid`, `json`, `logging`, `os`, `sys`,
  `time`, `xml.etree.ElementTree` — all work as expected.
- **C-accelerated stdlib types cannot be monkey-patched** — `xml.etree.ElementTree.Element` is a C
  type on cppython: you cannot add methods or subclass it. If a library uses lxml-specific methods
  like `iterchildren()` or `clear(keep_tail=True)`, patch the library source directly.
- **lxml can be replaced with a pure Python shim** — `xml.etree.ElementTree` covers most
  `lxml.etree` usage. Patch these in the library source:
  - `elm.iterchildren()` → `iter(elm)` or `list(elm)`
  - `elm.clear(keep_tail=True)` → `tail = elm.tail; elm.clear(); elm.tail = tail`
  - `etree.tostring()` → `ET.tostring(elm, encoding='unicode').encode('utf-8')` to avoid an
    unwanted `<?xml?>` declaration (lxml omits it; stdlib adds it with byte encodings). NEVER use
    `encoding='utf-8'` directly — it returns bytes *with* the declaration.
  - `etree.XMLSyntaxError` → `xml.etree.ElementTree.ParseError`
  - `etree.XMLPullParser` works on cppython — use it for streaming XML parsing

## Error Handling

Wrap API calls and log the error:

```python
try:
    data = cp.get('status/system')
    if data:
        # process data
except Exception as e:
    cp.log(f"Error getting system status: {e}")
```

## Local Development (Running on Your Computer)

Apps can run on your machine: `.venv/bin/python3 my_app/my_app.py` (Mac/Linux) or
`.venv\Scripts\python my_app\my_app.py` (Windows). `cp.py` detects it is not on a router and uses
HTTP REST against the dev router in `sdk_settings.ini`.

- **`cp.py` only finds `sdk_settings.ini` in the cwd and the cwd's PARENT.** For an app in
  `apps/my_app/`, running from inside the app folder finds nothing, and every call fails with
  `Invalid URL 'https:///api/...': No host supplied` while `wait_for_wan_connection()` spins until
  it times out. **Run local tests from `apps/`**: `.venv/bin/python3 my_app/my_app.py`.
- **Works locally**: `cp.get/put/post/delete` (via REST), and `cp.log()` prints to stdout.
- **Does NOT work locally**: `cp.alert()` (logs to console, never reaches NCM),
  `cp.register()`/`cp.unregister()` (needs the router's internal socket, no REST equivalent),
  `cp.decrypt()` (returns None), serial, and GPIO.
- **`cp.put()` returns a DIFFERENT envelope locally than on-router** — the on-router socket
  returns `{'status': 'ok'|'error'|'timeout', 'data': ...}`; local REST returns
  `{'success': True|False, 'data': ...}`. Code that only checks `success` silently treats every
  on-router failure as success. **Check both keys.**
- **Web servers bind to YOUR machine** — an app's HTTP server listens on your computer's port,
  not the router's, so LAN clients behind the router cannot reach it.
- **Use local runs for fast iteration** on API reads, data processing, and business logic. Deploy
  to the router to test alerts, events, web UIs, serial, and GPIO.
