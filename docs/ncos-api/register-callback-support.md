# `cp.register()` callback support by path

Which `status/` (and related) paths actually fire `cp.register()` callbacks on NCOS. Tested live
on the dev router (5G dual-modem model, NCOS 7.26 era, Nov 2026) with a temporary on-router probe
app. For every path the probe:

1. registered `put`, `set`, `post` and `delete` callbacks,
2. polled the same path once a second to learn whether its value really changed, and
3. triggered real events (GPIO writes, ethernet disable/enable, control-tree writes).

A path is only called "silent" below if its value was **seen to change** by polling while the
callback count stayed 0.

## Summary

| Path | Fires? | What triggers it |
|---|---|---|
| `control/**` (any write) | **Yes** | Any `cp.put`/REST PUT to it (reliable) |
| `status/<app_path>` written by an SDK app | **Yes** | Your own `cp.put('status/...')` |
| `status/ecm/state` | **Yes** | NCM state changes (`stopped` / `authorizing` / `connected`), several events per transition |
| `status/gps/fix` | **Yes** | About once per second while GPS is running (very chatty) |
| `status/wlan/state` | **Yes** | WiFi subsystem restart (`"Off"` then `"On"`) |
| `status/wlan/radio` | **Partly** | Radio reconfigure/restart (channel, power). Seen in bursts of ~7 |
| `status/ethernet` (whole array) | **Partly** | Config changes only (`enabled` toggled). **Not** link up/down |
| `status/gpio`, `status/gpio/<PIN>` | **No** | Pin changes (verified by polling) never fire |
| `status/ethernet/<n>`, `.../link`, `.../link_speed`, `.../enabled`, byte counters | **No** | |
| `status/wlan/clients`, `status/wlan/radio/0/clients` | **Not testable** | No WiFi client was connected, so no change ever happened. Unproven either way |
| `status/lan/clients` | **No** | Client list changed 4 times, 0 callbacks |
| `status/wan/primary_device` | **No (not reproduced)** | Changed twice in each of the runs I checked (`mdm-...` to `"None"` and back), 0 callbacks |
| `status/wan/connection_state` | **No** | |
| `status/wan/devices/<id>/status/{summary,connection_state,uptime}` | **No** | |
| `status/wan/devices/<id>/info/service_type` | **No** | Changed, 0 callbacks |
| `status/wan/devices/<id>/diagnostics` and `/SRVC_TYPE`, `/SS`, `/RSRP_5G` | **No** | Diagnostics changed ~19 times |
| `status/wan`, `status/wan/devices` (parents) | **No** | Parent registrations stayed silent while children changed |
| `status/system/uptime` | **No** | Changed every second, 0 callbacks |
| `status/dhcpd`, `status/ipverify`, `status/wan/devices/ethernet-wan/status/summary` | **Unproven** | Value never changed during the test |

## How matching works (from the control-tree and app-written status tests)

- **Only the action `put` is supported on this firmware.** `set` is rejected at registration
  (`{"status":"error","data":"'set'"}`). `post` and `delete` register `ok` but never fired in any
  test (not exercised by anything that issues a POST/DELETE to those paths).
- **Writes propagate both ways through the path tree** when the write goes through the config
  store. Writing the leaf `h/a/b` fired registrations on `h`, `h/a` and `h/a/b`. Writing the
  parent `h` (a dict) also fired the registration on `h/a/b`. This held for both `control/...`
  and an app-written `status/...` path.
- So a silent status path is not a registration mistake. NCOS daemons only emit events for the
  status values they publish through the config store. Many values (GPIO, ethernet link, WAN
  state, LAN clients) are updated without raising an event, even though a `GET` always shows the
  new value.
- Callback values can be stale. The `status/ethernet` callback on disabling port 1 still showed
  `link: up` with `enabled: false`. Re-`get` the specific path if you need current state.
- Callbacks arrive in duplicates (the same value 2 to 3 times in a burst), so de-bounce.

## Details per area

### GPIO
- `control/gpio/<PIN>` writes fire the callback on `control/gpio`, `control/gpio/<PIN>` (the
  value you wrote). They fire only for writes made through the control tree, and they carry the
  requested value, not the hardware result.
- `status/gpio/*` changed on every write (verified, e.g. `MODEM_GRN`, `CONNECTOR_GPIO_2`) and
  from system activity (`NCM_STATE`, `CELLHEALTH_GRN`, `MODEM_GRN` LED following WAN state) but
  never fired. **Poll `status/gpio/<PIN>`**. A 1 s poll caught every change.
- Watching an input pin (e.g. ignition) therefore needs polling. Callbacks will not do it.

### Ethernet
- `status/ethernet` (parent only) fires when `config/ethernet/<n>/enabled` changes.
- Cable plug/unplug (link up/down, speed change) fired nothing, on the parent or on any child.
  Observed: port 1 link went down then up during a disable/enable cycle, with no event for either
  transition. Poll `status/ethernet/<n>/link`.

### WiFi
- `status/wlan/state` and `status/wlan/radio` fire when the radio restarts or changes channel.
  Those are radio events, not client events.
- Client join/leave could not be tested (no client). `status/wlan/clients` was registered and
  stayed `[]`. Treat as unverified. Poll `status/wlan/clients` until someone verifies with a
  real client.

### WAN
- Not one of `connection_state`, `primary_device`, per-device `summary`, `info/service_type` or
  any `diagnostics` field fired. Each was seen changing, including a full modem
  `connecting` -> `connected` cycle and `primary_device` going `"None"` -> `mdm-...`.
- The earlier belief that `status/wan/primary_device` supports callbacks did **not** reproduce
  here (3 runs, at least 4 real changes). If it works elsewhere, it may depend on firmware or on the
  kind of change (e.g. a real failover between two devices). Treat as unreliable and keep a poll
  as backup.
- `service_type` lives at `info/service_type` (device-level, `5G`) and `diagnostics/SRVC_TYPE`.
  Both change silently. Poll them.

### Practical pattern
Use callbacks only where they are known to fire, and poll the rest:

```python
# fires: control tree, status/ecm/state, status/wlan/state, status/ethernet (config changes)
cp.register('put', 'status/ecm/state', on_ecm)

# silent: poll the narrowest path you can (single leaf, 1-2 s)
while True:
    link = cp.get('status/ethernet/1/link')
    pin = cp.get('status/gpio/CONNECTOR_GPIO_1')
    time.sleep(1)
```

## Not tested / caveats
- One router model and firmware. Other models may publish more or fewer paths via the config
  store.
- The WAN transitions seen were natural (a modem reconnect cycle, plus the ethernet disable
  test), not forced failovers between two active WAN devices.
- `post` and `delete` actions were never exercised, only registered.
- Test side effects: toggled `MODEM_GRN` and `CONNECTOR_GPIO_2` (power connector output) once
  each, disabled ethernet 2 (8 s) and ethernet 1 (12 s, brief loss of management access). All
  ports were re-enabled. `MODEM_GRN` read `0` afterwards because the system LED logic owns that
  pin and tracked WAN state.
