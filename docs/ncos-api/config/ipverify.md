# config/ipverify and config/identities/ipverify

<!-- path: config/ipverify -->
<!-- type: config -->

[config](README.md) / ipverify

---

IP Verify is the router's built-in connectivity testing subsystem. The path is **`ipverify`** —
there is no `ip_verify` or `connection_verify` path.

It is split into two arrays that must both be written:

- **`config/ipverify/{type}`** — the *test* (the probe mechanics)
- **`config/identities/ipverify`** — the *identity* (scheduling, retries, logging) which
  points at a test by its `_id_`

Results appear in **`status/ipverify/{identity_id}`**, keyed by the **identity** `_id_`, not
the test `_id_`.

## config/identities/ipverify

| Field | Type | Default |
|-------|------|---------|
| `_id_` | uuid | assigned by the router |
| `name` | string | `''`, max 30 chars, **`[a-zA-Z0-9_-]` only** |
| `type` | select | `ethernet_port_state`; also `ping`, `wan_device_state`, `vrrp_state`, `sfp_port_state`, `route_exist`, `bgp_peer`, `composite`, `custom`, `config_store` |
| `test_id` | uuid | `_id_` of the row in the matching `config/ipverify/{type}` array |
| `enabled` | boolean | `false` |
| `interval` | u16 | `30` (seconds) |
| `retry_count` | u32 | `5` (min 0, **max 5**) |
| `retry_interval` | u32 | `20` (**min 5, max 30**) |
| `log_on_pass` / `log_on_fail` | boolean | `false` |
| `alert_on_pass` / `alert_on_fail` | boolean | `false` |
| `debug` | boolean | `false` |

`log_on_*` and `alert_on_*` fire on **every run**, not on state changes, which floods the
log. Watch `status/ipverify` yourself and report transitions instead.

## config/ipverify/ping

| Field | Type | Default |
|-------|------|---------|
| `_id_` | uuid | assigned by the router |
| `ping_target` | ipany_or_dnsname | required |
| `pkt_interval` | u8 | `10` — **tenths of a second** |
| `pkt_timeout` | u8 | `10` — **tenths of a second** |
| `pkt_per_try` | u8 | `1` |
| `pkt_size` | u16 | `36` (**minimum 36**) |
| `source_ip` | ipany | `''` |
| `wan_trigger_field` | select | `type`, `port`, `pdn`, `manufacturer`, `model`, `serial`, `mac`, `uid`, `config_id` |
| `wan_trigger_predicate` | select | `is`, `is not`, `starts with`, `contains`, `ends with` |
| `wan_trigger_value` | string | `''`, max 100 |
| `wan_trigger_neg` | boolean | `false` |

### WAN binding

`wan_trigger_*` selects which WAN device the probe is sourced from. The field options map
onto `status/wan/devices/{uid}/info` keys.

**There is no `sim` option.** For a DSDS modem, both SIM slots share `port` *and*
`config_id`, so neither can pin a test to one slot — `uid` is the only field that reliably
can. Note `wan_trigger_value` takes the bare hex from `info/uid` (`5a3e6e08`), not the
`mdm-` prefixed key used in status paths.

```python
cp.post('config/ipverify/ping', {
    'ping_target': '8.8.8.8',
    'wan_trigger_field': 'uid',
    'wan_trigger_predicate': 'is',
    'wan_trigger_value': '5a3e6e08',
})
```

## Gotchas

- **A test bound to a DISCONNECTED device reports `pass: false`, not "no result".** WAN
  binding does *not* gate on connection state, so a standby device is indistinguishable
  from a real outage. To make a test genuinely stop running, set its identity's
  `enabled` to `false`, which removes its key from `status/ipverify` entirely.
- **`pass` has three states: `True`, `False`, and `''`.** The empty string means no verdict
  yet (just created, or the poller restarted). Treating `''` as a failure is the classic
  trap.
- **Any write to IP Verify config restarts the poller**, blanking *every* test's result to
  `''` for up to `interval + retry_count × retry_interval` seconds — including tests you
  did not touch. Only write when the desired state actually changed, and wait out that
  window before trusting results.
- **POST returns the new entry's array INDEX, not its UUID.** Read `_id_` back before
  referencing it:
  ```python
  idx = cp.post('config/ipverify/ping', {...})['data']
  test_id = cp.get('config/ipverify/ping/%s/_id_' % idx)
  ```
- **`name` only allows `[a-zA-Z0-9_-]`** — no dots, no pipes. Translate them:
  `'8.8.8.8'` → `'8_8_8_8'`. 30 character limit.
- **Deleting shifts array indexes.** Collect indexes, delete highest first, and delete
  identities before the tests they point at.
- **There is no HTTP test type.** For an HTTP connectivity check, perform it in the app and
  bind the socket's source address to the WAN device's
  `status/wan/devices/{uid}/status/ipinfo/ip_address`:
  ```python
  conn = http.client.HTTPConnection(host, 80, timeout=10,
                                    source_address=(wan_ip, 0))
  ```
  This works on-router. Running an app locally it fails with
  `OSError: [Errno 49] Can't assign requested address`, since the dev machine does not hold
  the router's WAN IP.

## config/ipverify/wan_device_state

Pure device-state test, no probe traffic.

| Field | Type | Default |
|-------|------|---------|
| `all` | boolean | `false` — all matching devices vs any |
| `state` | select | `connected`; also `disconnected`, `standby` |
| `trigger_field` | select | `uid`; same option list as `wan_trigger_field` |
| `trigger_predicate` | select | `is` |
| `trigger_value` | string | `''`, max 100 |

## Other test types

`bgp_peer` (`peer`), `composite` (`expr`), `config_store` (`cs_path`/`cs_value`/`option`),
`custom` (`name`), `ethernet_port_state` (`port`), `route_exist`
(`dev`/`gw`/`ip_network`/`metric`/`table_id`), `sfp_port_state` (`uid`), `vrrp_state`
(`is_master`/`lan_id`).

## Consumers

Other subsystems reference a test via a `{test_id, on_pass}` struct:
`config/vpn/tunnels/ipverify` (+ `change_tunnel_state`), `config/lan/vrrp/ipverify`
(+ `priority_adj`), `config/dns/dns_override/ipverify` (+ `actions`),
`config/routing/route_map/entry/matches|sets/ipverify`. Alerts:
`config/alerts/ipverify_event` and `ipverify_event_limit`.

## See Also

- [status/wan/devices/dsds](../status/wan/devices/dsds.md) — per-SIM binding on DSDS modems
- `apps/dsds_wan_verify/` — creates, gates, and reconciles per-slot ping tests
- `client_monitor/` — per-client ping test lifecycle
