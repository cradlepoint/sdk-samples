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
