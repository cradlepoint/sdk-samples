---
inclusion: auto
description: "Cradlepoint NCOS API reference and cp module usage guidelines"
---
# Cradlepoint NCOS API Reference

## CP Module

- Always `import cp` and use module-level functions when possible
- Never use EventingCSClient or CSClient classes
- **ALWAYS check @cp.py for helper functions before using direct API calls**
- **NEVER make up function names** - if you don't know what functions exist, read @cp.py first
- cp.py helpers are for simple use cases and may return minimal data — for detailed data, prefer direct API calls
- **cp.get() returns data directly, NOT wrapped in {"success": true, "data": ...}** - the wrapper is only in raw HTTP API responses
- **ALWAYS use cp.get_appdata('field_name') with a field name** - never call without args to get all appdata
- cp.get_appdata() without args returns a LIST of dicts, not a dict
- **cp.put_appdata(name, value) takes TWO arguments** - name and value as separate strings, NOT a dict
- Appdata is stored in config, not status: `config/system/sdk/appdata`
- **NEVER write default values to appdata** - This overrides NCM group configs. Read appdata, use a code default if missing
- Document all appdata fields in readme.md, mark required fields

## NCOS API Documentation

- **Full API docs**: `docs/ncos-api/` - status, config, control, and state APIs
- **Quick reference**: `docs/ncos-api/README.md` - common tasks and examples
- **Detailed structures**: `docs/ncos-api/api-structures.md` - all API response formats, patterns, and gotchas
- **Status API** (read-only): WAN, GPS, modem, system - see `docs/ncos-api/status/`
- **Config API** (settings): 500+ paths - see `docs/ncos-api/config/PATHS.md`
- **Control API** (actions): reboot, ping, GPIO - see `docs/ncos-api/control/`
- **DTD API** (structure): `/api/dtd/config/path` shows exact field types and requirements
- **When searching for an API path**: use `grep -r "keyword" docs/ncos-api/status/ --include="*.md"`
- Use `cp.get('status/path')` for reads, `cp.put('control/path', value)` for actions
- **Control API via REST**: Use form data: `curl -u admin:pass -X PUT http://router/api/control/path -d "data=value"` (NOT JSON)
- **Config API via REST**: Also uses form data: `curl -k -u admin:pass -X POST https://router/api/config/path/ -d 'data={"key":"val"}'` (NOT JSON body)
- **Control API via SDK**: Use `cp.put('control/path', value)` - SDK handles encoding automatically
- **Appdata via REST**: Read: `GET /api/config/system/sdk/appdata/`, Create: `POST ... -d 'data={"name":"field","value":"val"}'`, Delete: `DELETE .../appdata/{_id_}`

**See `#rtfm.md` for the full API verification workflow before writing any API code.**

## Key Gotchas (Quick Reference)

- status/lan/clients does NOT have rx_bytes/tx_bytes — use status/client_usage
- QoS rules do NOT support MAC addresses — only IP addresses via lipaddr/lmask
- Firewall conntrack entries have unique 'id' field — track by ID to avoid counting stale connections
- ARP dump interface names have trailing digits — strip them before looking up network info
- **GPS injection**: Write scalar sub-paths (`fix/lock`, `fix/latitude` as dict, `lastpos/latitude`, etc.) + `status/gps/devices/None/current_nmea` with 0.5s keepalive loop. GPS must be enabled with keepalive. Use `control/gps/stop` each cycle. **May only work reliably from NCM-installed apps** (production SDK mode) — dev-mode SCP installs appear to have lower privilege for status tree writes that reach WPC. See `connected_ems_vehicle/ncm_client.py` for the confirmed working pattern and `docs/ncos-api/status/gps.md`
- Firewall filter policies require full rules array put — cannot update individual rules
- Log entry format: `[timestamp, facility, level, message]` — filter by recency after deploys
- Cert creation is async — wait ~5 seconds after `cp.put('control/certmgmt/ca', {...})`
- IP Verify identity names only allow `[a-zA-Z0-9_-]` — no dots. Replace dots with underscores: `target_ip.replace('.', '_')`
- `cp.register` callback receives 3 args: `(path, value, args)` where `args` is a single tuple — do NOT use `*args` unpacking in the callback signature
- SCP "lost connection" during `make.py install` is normal — the router drops the SSH connection after receiving the file. Exit code 1 is expected
- IP Verify identity `name` field only allows `[a-zA-Z0-9_-]` — no dots. Replace dots with underscores (e.g., `'SDK-' + ip.replace('.', '_')`)
- **`cp.register()` for control tree paths MUST use `'put'` (lowercase) as the action** — `cp.register('put', 'control/...', callback)`. Using `'set'` or `'PUT'` (uppercase) silently fails to trigger callbacks
- **Do NOT `cp.put()` to seed the control tree before `cp.register()`** — the dict PUT response causes socket desync, making subsequent register calls fail silently. Register first, then seed (or don't seed at all)
- **Control tree keys persist across app redeploys** — the router merges control tree writes, never replaces. Renaming control paths leaves stale keys until router reboot. Keep control path names stable to avoid confusion

**For detailed API structures, response formats, and code patterns, see `#[[file:docs/ncos-api/api-structures.md]]`**

## Packet Capture (tcpdump) API

- **tcpdump is a REST-only API** — it does NOT work via `cp.get()` socket dispatch. You must use HTTP with Basic Auth
- **Pattern**: `GET http://{router_ip}/api/tcpdump/{filename}.pcap?iface=...&args=...&timeout=...&count=...&url=...`
- **The request blocks** until the capture completes (timeout or count reached), then returns pcap binary data
- **Requires user credentials** — use `cp.ensure_fresh_user('SDKTCPDUMP', 'admin')` to create a temp user with a random password, then use those creds for HTTP Basic Auth
- **CAUTION with ensure_fresh_user passwords** — the generated password contains special chars (`!@#$%^&*`) that can break HTTP Basic Auth. Instead use `cp.delete_user()` + `cp.create_user()` with an alphanumeric-only password (e.g., `hashlib.md5(str(time.time()).encode()).hexdigest()[:16]`)
- **Router IP on-device**: Use `cp.get('config/lan/0/ip_address')` or `127.0.0.1`
- **Clean up**: Delete the temp user after capture with `cp.delete_user('SDKTCPDUMP')`
- **Auth propagation delay** — after creating a user, the router's shadow password system needs time to propagate. Wait 3+ seconds after delete (clears stale shadow), then verify auth works with a test GET before using the credentials. The router log shows "Removing stale shadow password for: USERNAME" during cleanup — if you authenticate too soon after creation, you get 401
- **Parameters**: `iface` (interface), `args` (BPF filter), `timeout` (seconds), `count` (packets), `url` (upload URL for CloudShark), `wifichannel`, `wifichannelwidth`, `wifiextrachannel`
- **iface value for LAN networks** — use the UUID from `config/lan[]/_id_` (e.g., `00000000-0d93-319d-8220-4a1fb0372b51`), NOT the device iface name. This matches how the NCOS UI sends it
- **Do NOT use `cp.start_packet_capture()`** for on-router apps — it calls `get()` which can't handle binary pcap responses correctly
