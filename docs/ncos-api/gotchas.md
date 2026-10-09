# NCOS API Gotchas — Verified Findings

Long-form notes on API behavior that is surprising, undocumented, or contradicts what
"should" be true. Each entry was confirmed on a real router.

`.kiro/steering/api-reference.md` carries a one-line index of these. This file has the detail.

Search it: `grep -n "keyword" docs/ncos-api/gotchas.md`

---

## Config write semantics

- **A partial dict PUT to a config struct path MERGES, it does not replace** — unlisted keys keep their values, and the response returns the full merged struct. Verified on `config/system/serial`.

- **A config PUT to a path the model does not support can return an `ok` envelope and apply NOTHING** — on an E3000, `cp.put('config/system/rtk/ntrip', {...})` returned `{'status': 'ok'}` over the on-router socket while the router logged `[root] UNHANDLED PUT ERROR` and wrote nothing. The same path over REST correctly returned `{"success": false, "data": {"exception": "key", "key": "rtk"}}`. **Never trust a config PUT response alone — read the value back and compare.** To detect model support up front, `cp.get('config/system/<feature>')` returns `None` and `/api/dtd/config/system/<feature>` returns `{"exception": "key", ...}` when the feature does not exist on that model.

- **A config write that reports success may not have applied — read it back before caching "done"** — bit me on `config/identities/ipverify/{idx}/enabled`: a dict-merge PUT returned ok, the value did not change, and because the caller cached a "state applied" signature nothing ever retried, leaving a standby SIM's ipverify test armed indefinitely (which reads as a hard failure). Two habits that fix it: PUT a **scalar leaf** (`.../{idx}/enabled`) rather than folding the field into a dict merge, and read the value back and compare before recording the state as applied. Applies to any reconcile loop that skips work when "nothing changed".

- **Write cross-validated config structs in ONE PUT, never leaf by leaf** — some structs validate across fields, so per-leaf writes make the router validate each intermediate state. A legal end state gets rejected partway through AND the leaves already written stay applied, leaving config half-changed. A single struct PUT is validated as a whole and is all-or-nothing. Concrete case: `config/system/serial/flow_control` rejects `hardware` and `software` both true (`"Software and Hardware flow controls cannot be configured together."`), so switching between them one leaf at a time always fails.

- **REST config PUT of a STRING leaf needs JSON quoting** — `-d 'data="ttyUSB0"'` works, `-d 'data=ttyUSB0'` returns `{"exception": "server", "reason": "Expecting value: line 1 column 1 (char 0)"}`. Numbers and booleans are bare. `cp.put()` serializes for you, so this only affects raw curl.

- **Feature-gated config subtrees are absent, not empty** — RTK is a good example: `config/system/rtk` and `status/rtk` are both `null` on models without RTK support (E3000), while an RTK-capable model (R2400) has a populated `config/system/rtk/ntrip` struct (`format`, `gga_rate`, `host`, `mountpoint`, `port`, `username`, `password`). Gate on the parent path existing before writing.

- **An app's config-save API should MERGE incoming fields over stored values, not rebuild from defaults** — a client written against an older field set (a browser tab left open across an app upgrade, or a script posting a partial object) otherwise silently blanks every field it does not know about, since the unknown keys fall back to code defaults. Merging per field still lets a client clear a value, because it sends complete values for the fields it does know.

## Status tree

- **An app can publish its own JSON to a NEW status path, and that PUT REPLACES (unlike config)** — `cp.put('status/my_app', {...})` creates the path and works from a dev-mode SCP install as well as over REST. A second dict PUT drops keys that are not in it, so every write must be the complete object. The value lives in RAM: not size capped, not persisted across reboot, and it outlives the app (stopping the app leaves the last value there), so include a timestamp consumers can check for staleness. This is the right place for detailed app state that does not fit a 255-char config field like `config/system/asset_id`.

- **`status/dhcpd` is `null`, not `{'leases': []}`, when the router's LAN DHCP server is disabled** (`config/lan/0/dhcpd/enabled = false`). `cp.get('status/dhcpd') or {}` handles it, but code that treats "no leases" as evidence about client devices needs to know the router may not be serving DHCP at all. There is no `dtd` for it (`/api/dtd/status/dhcpd` returns a `key` exception).

- **`status/lan/clients` does NOT have `rx_bytes`/`tx_bytes`** — use `status/client_usage`.

- **Log entry format is `[timestamp, level, facility, message, extra]`** — level (`INFO`, `ERR`) is index 1, facility (`client_monitor`, `kernel`) is index 2, message is index 3. Filtering on index 1 for an app name silently matches nothing. Filter by recency after deploys.

## Routing

- **`config/routing/policies` entries have NO `_id_` field** — routing tables DO have an `_id_` UUID, routing policies do not (confirmed in the DTD and on-device). A policy is addressable ONLY by its numeric collection index, returned in the POST response `data`. `policy.get('_id_')` always returns `None`, which makes "find existing policy" checks always miss (duplicate policies pile up, array caps at 100) and makes deletes silent no-ops. Identity model: `table_id` = table UUID, `policy_index` = policy numeric index. See `config/source-routing.md`.

- **Deleting from `config/routing/policies` or `config/routing/tables` must go highest index to lowest** — both are arrays, so deleting one entry shifts the indexes of all later entries. Collect indexes, `sorted(reverse=True)`, then delete. Delete policies before the tables they reference.

## WAN rules and modems

- **`config/wan/rules2/priority` is LOWER = more preferred, not higher** — the DTD gives no direction and older docs in this repo claimed the opposite. The stock R2400 ordering (Wbond -10, Ethernet 1, 5G/LTE 1.5, Satellite 1.7, LTE-only 2, WiFi-as-WAN 4, 3G-only 5) matches NCOS's default WAN preference exactly when read ascending. Also: **both DSDS SIM slots share one rule and therefore one priority**, so WAN rule priority cannot express a preference between them — an app needing a preferred slot must carry its own setting. See `config/wan-rules2.md`.

- **DSDS modems: each SIM slot is a separate `mdm-*` device, and `info/port` + `info/config_id` are IDENTICAL on both** — identify slots by `info/port` + `info/sim`, never by port or `config_id` alone. `diagnostics/DISP_IMEI` is shared too, but `info/serial` is NOT (it carries the per-slot `CGSN`). Switch slots with `cp.put('control/wan/devices/{connected_uid}/testmode/dsds_switch', True)` — sent to the **connected** slot, returns in ~0.1s, completes in **29–37s**. `summary` of `Dual SIM switch` / `sibling transitioning` means a switch is in flight; `isActiveSib` flips halfway so it is NOT a readiness signal (use `connection_state == 'connected'`). Device UIDs are stable across a switch. The `dsds_switch` key may be absent from `testmode` before the first PUT and persists on both slots after, so never gate on it. See `status/wan/devices/dsds.md`.

- **Which modem signal metrics exist depends on the live radio technology, not the modem** — 5G SA reports ONLY `RSRP_5G`/`RSRQ_5G`/`SINR_5G` (no `DBM`/`RSRP`/`RSRQ`/`SINR`), LTE reports only the LTE set, and 5G NSA reports BOTH. A modem moves between these without reconnecting, so re-read the available keys every poll instead of assuming `DBM` exists. A **DSDS standby slot still reports live diagnostics and `cellular_health_score`**, which is the only way to judge a disconnected slot (`signal_backlog` samples hourly — far too stale). Some diagnostics fields carry the literal string `'None'` rather than being omitted (e.g. `SRVC_TYPE_DETAILS` on a standby slot), so normalize `''`/`'None'`/`'Unknown'` to absent.

## IP Verify

- **An IP Verify test bound to a DISCONNECTED WAN device reports `pass: false`, not "no result"** — `wan_trigger_*` binding does NOT gate on connection state, so a standby device looks identical to a real outage. This matters most on DSDS modems, where the standby SIM slot would permanently read as failed. To make a test actually stop running, set its identity's `enabled` to `false`, which removes its key from `status/ipverify` entirely. Also: **any write to IP Verify config restarts the poller**, blanking *every* test's result to `''` for up to `interval + retry_count × retry_interval` seconds — including tests you did not touch. Only write when the desired state changed. See `config/ipverify.md`.

- **`config/ipverify/ping`'s `wan_trigger_field` has NO `sim` option** — the options are `type|port|pdn|manufacturer|model|serial|mac|uid|config_id`. On a DSDS modem both SIM slots share `info/port` **and** `info/config_id`, so only `uid` can pin a test to one slot. `wan_trigger_value` wants the bare hex from `info/uid` (`5a3e6e08`), not the `mdm-` prefixed status key. **There is no HTTP test type at all** — do HTTP checks in the app with `http.client.HTTPConnection(host, port, timeout=t, source_address=(wan_ip, 0))`, which binds the probe to one WAN device (works on-router; fails locally with `Errno 49 Can't assign requested address`).

- **IP Verify identity `name` only allows `[a-zA-Z0-9_-]`** — no dots. Replace them: `'SDK-' + ip.replace('.', '_')`.

## Serial

- **`config/system/serial/byte_parity` is 0=None, 1=Even, 2=Odd, 3=Mark, 4=Space** — Even is 1, NOT 2. Mapping it to pyserial with Even/Odd swapped silently misconfigures the line. `stop_bits` is 0=1, 1=1.5, 2=2. See `config/serial.md`.

## Time and timezone

- **On-router `time.localtime()` is already router-local, but `time.strftime('%Z')` lies** — the router sets `TZ` for SDK app processes from `config/system/timezone`, so local time and `%z` are correct on-device (verified: `%z` gave `-0600` matching the router's own log clock, and it tracks DST). But `config/system/timezone` is a bare offset (`"+7"`), which makes `status/system/tz` read `UTC+7UTC+6,M3.2.0,M11.1.0` — both variants named `UTC` — so `%Z` returns `"UTC"` on a router sitting at UTC-06:00. Publish the numeric offset from `%z` (plus `tm_isdst`) as the timezone indicator, never the abbreviation. Also note **POSIX TZ signs are inverted**: `UTC+7` in that string means UTC−7, so don't parse `status/system/tz` to get an offset.

## SDK mechanics

- **`cp.register` callback receives 3 args: `(path, value, args)`** where `args` is a single tuple — do NOT use `*args` unpacking in the callback signature.

- **`cp.register()` for control tree paths MUST use `'put'` (lowercase)** — `cp.register('put', 'control/...', callback)`. Using `'set'` or `'PUT'` (uppercase) silently fails to trigger callbacks.

- **Do NOT `cp.put()` to seed the control tree before `cp.register()`** — the dict PUT response causes socket desync, making subsequent register calls fail silently. Register first, then seed (or don't seed at all).

- **Control tree keys persist across app redeploys** — the router merges control tree writes, never replaces. Renaming control paths leaves stale keys until router reboot. Keep control path names stable.

- **Password hashes: the REST API returns a masked `$0$` format** — only the SDK socket (on-router) returns the real `$3$` PBKDF2-SHA256 hash. Salt in `$3$iters$salt$key` is raw ASCII string bytes, NOT base64-decoded. `cp.validate_password()` is on-router only.

- **SCP remote path MUST be `/app_upload`** (no trailing slash) — `/app_upload/` causes an "invalid filename" rejection. Use `scp -O` (legacy protocol); the router's CradlepointSSHService does not support SFTP. A "lost connection" during `make.py install` is normal — the router drops the SSH connection after receiving the file, and exit code 1 is expected.

## Other APIs

- **QoS rules do NOT support MAC addresses** — only IP addresses via `lipaddr`/`lmask`.
- **Firewall filter policies require a full rules-array PUT** — individual rules cannot be updated.
- **Firewall conntrack entries have a unique `id` field** — track by ID to avoid counting stale connections.
- **ARP dump interface names have trailing digits** — strip them before looking up network info.
- **Cert creation is async** — wait ~5 seconds after `cp.put('control/certmgmt/ca', {...})`.

## External (non-NCOS) APIs

- **GraphQL: a field you did not request is absent, not empty — and a local re-check on that field silently matches nothing** — hit with the Point One API: `myDevices(filter: {tag: ...})` filtered correctly server-side, but the shared selection-set fragment omitted `tags { key value }`, so every returned device had `tags == None`. A defensive local re-filter (`[d for d in found if tag(d, k) == v]`) then discarded every result, making "find my existing device" always miss and recreate it. When adding a filter on a field, verify that field is in the selection set. A mock/fake backend will not catch this because fakes return whole objects — test identity lookups against the real API.

> The NCM API's lack of CORS support is documented in `.kiro/steering/web-standards.md`, which is
> always in context — not repeated here.
