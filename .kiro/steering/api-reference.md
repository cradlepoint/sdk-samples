# Cradlepoint NCOS API Reference

## API Verification Workflow (MANDATORY)

**Before writing ANY code that uses a `cp.get`/`cp.put` path or REST endpoint, complete these
steps IN ORDER. Do not write code first.**

1. **SEARCH docs**: `grep -r "keyword" docs/ncos-api/ --include="*.md"`
2. **READ the doc** — understand the response structure, fields, and usage patterns
3. **CHECK DTD** (config paths): `curl -s -u admin:pass http://router/api/dtd/config/path | .venv/bin/python -m json.tool`
4. **TEST the endpoint**: `curl -s -u admin:pass http://router/api/status/path | .venv/bin/python -m json.tool`
5. **VERIFY fields** — only use fields you have seen in a real response or a documented example
6. **THEN write code** — based on verified structure, not assumptions

No router available? Still do steps 1–2, and say which fields are unverified.

**NEVER:** assume a field exists because it "makes sense" · invent an API structure · write code
first and verify later · use SSH for API validation (always REST with `curl -u admin:pass`).

## CP Module

- Always `import cp` and use module-level functions. Never use `EventingCSClient` or `CSClient`.
- **Read `cp.py` before calling a helper** — never guess a function name. The helpers cover simple
  cases and may return minimal data; for detailed data prefer a direct API call.
- **`cp.get()` returns data directly**, NOT wrapped in `{"success": true, "data": ...}` — that
  wrapper only appears in raw HTTP REST responses.
- **`cp.get_appdata('field_name')` always takes a field name.** Called with no args it returns a
  LIST of dicts, not a dict.
- **`cp.put_appdata(name, value)` takes TWO string arguments**, not a dict.
- Appdata lives in config, not status: `config/system/sdk/appdata`.
- Document every appdata field in `readme.md` and mark which are required.

## Documentation map

| What | Where |
|---|---|
| Common tasks, quick reference | `docs/ncos-api/README.md` |
| Response formats and patterns | `docs/ncos-api/api-structures.md` |
| **Verified gotchas, long-form** | **`docs/ncos-api/gotchas.md`** |
| Status API (read-only) | `docs/ncos-api/status/` |
| Config API (500+ paths) | `docs/ncos-api/config/PATHS.md` |
| Control API (actions) | `docs/ncos-api/control/` |
| `cp` helper signatures | `docs/cp_methods_reference.md` |
| Live response explorer | `.venv/bin/python docs/ncos-api/explore_status.py status/wan/devices` |

`/api/dtd/config/<path>` shows exact field types and requirements for any config path.

## Request encoding

- **SDK**: `cp.get('status/path')` to read, `cp.put('control/path', value)` to act. `cp.put()`
  handles encoding for you.
- **REST control**: form data — `curl -u admin:pass -X PUT http://router/api/control/path -d "data=value"` (not a JSON body)
- **REST config**: also form data — `curl -k -u admin:pass -X POST https://router/api/config/path/ -d 'data={"key":"val"}'`
- **REST appdata**: read `GET /api/config/system/sdk/appdata/`, create `POST ... -d 'data={"name":"field","value":"val"}'`, delete `DELETE .../appdata/{_id_}`

## Gotcha index

One line each. **Full detail and reproduction notes in `docs/ncos-api/gotchas.md`** — read the
entry there before acting on anything in this list.

**Config writes**
- A partial dict PUT to a config struct MERGES, it does not replace
- A config PUT to a path the model does not support can return `ok` and apply nothing
- A config write that reports success may not have applied — read it back before caching "done"
- Write cross-validated structs in ONE PUT, never leaf by leaf
- Feature-gated subtrees (e.g. `config/system/rtk`) are absent, not empty
- REST config PUT of a string leaf needs JSON quoting (`data="ttyUSB0"`)
- An app's own config-save API should merge incoming fields, not rebuild from defaults

**Status tree**
- An app can publish JSON to a new `status/<app>` path, and that PUT REPLACES (unlike config)
- `status/dhcpd` is `null`, not `{'leases': []}`, when LAN DHCP is disabled
- `status/lan/clients` has no `rx_bytes`/`tx_bytes` — use `status/client_usage`
- Log entries are `[timestamp, level, facility, message, extra]` — app name is not in index 1

**Routing / WAN / modems**
- `config/routing/policies` entries have NO `_id_` — addressable only by numeric index
- Deleting from `config/routing/policies` or `tables` must go highest index to lowest
- `config/wan/rules2/priority` is LOWER = more preferred
- DSDS: each SIM slot is a separate `mdm-*` device; `info/port` and `info/config_id` are identical on both
- Which modem signal metrics exist depends on the live radio technology, not the modem

**IP Verify**
- A test bound to a disconnected WAN reports `pass: false`, not "no result"
- Disabling an identity leaves its stale `pass` in `status/ipverify` forever — track what you armed
- `wan_trigger_field` has no `sim` option, and there is no HTTP test type
- Identity `name` allows only `[a-zA-Z0-9_-]` — replace dots with underscores
- Any write to IP Verify config restarts the poller and blanks every test's result

**SDK mechanics**
- `cp.register` callbacks receive `(path, value, args)` — do not use `*args`
- `cp.register()` on control paths must use `'put'` (lowercase)
- Do not `cp.put()` to seed the control tree before `cp.register()` — causes socket desync
- Control tree keys persist across redeploys — keep path names stable
- REST returns masked `$0$` password hashes; only the on-router socket returns real `$3$`
- SCP remote path must be `/app_upload` with no trailing slash

**Other**
- On-router `time.strftime('%Z')` returns `"UTC"` even off UTC — publish `%z` instead
- `config/system/serial/byte_parity`: Even is **1**, Odd is 2
- QoS rules support IP only, no MAC · firewall filter policies need a full rules-array PUT
- Cert creation is async — wait ~5s after `cp.put('control/certmgmt/ca', ...)`

## Topic deep dives

Already documented in full — grep these rather than re-deriving:
`config/serial.md` · `config/ipverify.md` · `config/wan-rules2.md` · `config/source-routing.md`
· `status/rtk.md` · `status/gps/` · `status/wan/devices/dsds.md` · `control/tcpdump.md`
· `control/container.md` · `client-usage-qos.md`

Netperf/speed testing: activate `speedtest-standards`. GPS/NMEA/RTK: activate `gps-standards`.
