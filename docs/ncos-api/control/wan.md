# control/wan

<!-- path: control/wan -->
<!-- type: control -->
<!-- response: object -->

[control](../) / wan

---

WAN control: reset stats, device actions, steering.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `reset_stats` | null | PUT to reset WAN stats |
| `powersave` | null | Powersave control |
| `mdms_ready` | boolean | Modems ready (read-only) |
| `devices` | object | Per-device controls, see sub-table |
| `steering` | object | reset_stats, reload_rules |

**devices.{device_id}** (e.g. mdm-41949674, ethernet-wan)

| Field | Type | Description |
|-------|------|-------------|
| `reset_stats` | null | Reset device stats |
| `reset` | null | Reset device |
| `manual_activate_connect` | null | Manual activation connect |
| `manual_activate_started` | null | Manual activation started |
| `manual_activate_done` | null | Manual activation done |
| `manual_activate_finalize` | null | Manual activation finalize |
| `fw_upgrade` | null | Firmware upgrade |
| `activity` | null | Activity trigger (modems) |
| `factory_defaults_finalize` | null | Factory defaults (modems) |
| `puk_unlock` | null | PUK unlock (modems) |
| `restore_bands` | null | Restore bands (modems) |
| `euicc` | null | eUICC (modems) |
| `ob_upgrade` | object | Over-the-air upgrade |
| `remote_upgrade` | object | Remote upgrade URL |
| `testmode` | object | Test mode (reset, ready, shutdown) |

### eUICC (eSIM) profiles

eSIM-capable modules (e.g. Internal 5GF-NA eSIM, `MFG_MDL` `FE990B40-NAD`)
expose their installed profiles in `status/wan/devices/<uid>/diagnostics` and
are switched via the `euicc` control endpoint. Physical-SIM modules
(e.g. `FN990A28-CP`) do NOT publish these fields — the feature is absent, not
empty, and the control path reads back `null`.

**Detect support** (diagnostics fields): `EUICC_SGP22 == "TRUE"`, plus `EID`
(the eUICC identifier, required for activation) and `ESIM_TYPE`.

**Profile fields** — one `EUICC_PROF<n>` per installed profile, each a
comma-separated string. Field order matches the router's eSIM Manager UI
columns:

| index | field | eSIM Manager column |
|-------|-------|---------------------|
| 0 | ICCID | ICCID |
| 1 | profile name | Profile Name |
| 2 | active (`1`=active, `0`=not) | Active |
| 3 | nickname (may be empty) | Nickname |
| 4 | service provider | Service Provider |
| 5 | class (`0`=test, `2`=operational) | Class |
| 6 | reserved/padding (ignore) | — |

Example:
```
EUICC_PROF3": "8901882014725970045F,T-Mobile,1,W2255-SIM1-TMO,T-Mobile,2,0000000000000000"
```
= ICCID `8901882014725970045F`, name `T-Mobile`, active, nickname
`W2255-SIM1-TMO`, provider `T-Mobile`, class operational. The string carries NO
PLMN/MCC/MNC — correlate a profile to a carrier by name.

**Activate (enable) a profile** — PUT `control/wan/devices/<uid>/euicc`:
```python
import cp
cp.put('control/wan/devices/mdm-84e7b418/euicc', {
    'eid': '89033023426300000000057092735352',  # diagnostics EID
    'op_id': 0,
    'action': 'set_state',
    'payload': {'iccid': '8901882014725970045F', 'state': 'enable'},
})
```
Enabling makes the modem re-register on that carrier (brief connection drop;
may reset the modem if it needs different firmware).

### SDK Example
```python
import cp
# Reset WAN stats
cp.put('control/wan/reset_stats', None)
# Reset specific modem stats
cp.put('control/wan/devices/mdm-41949674/reset_stats', None)
# Reload steering rules
cp.put('control/wan/steering/reload_rules', True)
```

### REST
```
PUT /api/control/wan/reset_stats
PUT /api/control/wan/devices/mdm-{uid}/reset_stats
```

### Related
- [status/wan](../status/wan/README.md) - WAN status
- [config/wan/rules2](../config-wan-rules2.md) - WAN rules
