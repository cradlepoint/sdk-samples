# control/wlan

<!-- path: control/wlan -->
<!-- type: control -->
<!-- response: object -->

[control](../) / wlan

---

WLAN control: enable/disable, kick client, block MACs, radio inhibit.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `enable` | boolean | Master WLAN enable |
| `kick_mac` | string\|null | PUT MAC to kick client |
| `block_macs` | array | List of blocked MACs |
| `monitor_mode` | boolean | Monitor mode |
| `standby` | boolean | Standby mode |
| `radio` | array | Per-radio controls |

**radio[{index}]**

| Field | Type | Description |
|-------|------|-------------|
| `bss` | array | Per-BSS inhibit |
| `bss[].inhibit` | boolean | Inhibit BSS |
| `ui_channel_list` | array | Channel list |
| `region_selection` | string | Region (e.g. US) |
| `indoor_channels` | boolean | Indoor channels |
| `dfs_disabled` | boolean | DFS disabled |

**analytics**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Analytics enabled |
| `sample_period` | number | Sample period |

### SDK Example
```python
import cp
# Enable WLAN
cp.put('control/wlan/enable', True)
# Kick client by MAC
cp.put('control/wlan/kick_mac', '02:e0:5b:29:d5:eb')
# Block MAC (modify block_macs array via config or control)
```

### REST
```
PUT /api/control/wlan/enable
Body: true
PUT /api/control/wlan/kick_mac
Body: "02:e0:5b:29:d5:eb"
```

### Related
- [status/wlan](../status/wlan.md) - WLAN status
- [config/wlan](../config/PATHS.md) - WLAN configuration
