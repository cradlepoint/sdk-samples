# status/lan – devices

<!-- path: status/lan/devices -->
<!-- type: status -->

[status](../) / [lan](../lan.md) / devices

---

Per-device object. Returned as `status/lan` → `devices`.

### Structure

**devices.{device_id}**

| Field | Type | Description |
|-------|------|-------------|
| `info` | object | Device info (varies by type) |
| `stats` | object | Device stats |
| `status` | object | Device status |

Devices may be ethernet-lan, wlan-wireless0, etc. Structure varies by type.

### WLAN SSID Mapping

WLAN device names in `status/lan/devices` do NOT include SSID. To get the SSID for a WLAN device, use positional mapping from `config/wlan`:

- `wlan-wireless0` → `config/wlan[0]/bss[0]/ssid`
- `wlan-wireless0_1` → `config/wlan[0]/bss[1]/ssid`
- `wlan-wireless1_1` → `config/wlan[1]/bss[1]/ssid`

Pattern: `wlan-wireless{radio_index}_{bss_index}` (where `_0` is omitted).

**Important:** `config/wlan` returns a **dict**, not a list. Radios are at `config/wlan['radio']` (a list). Each radio has a `bss` list containing dicts with `ssid` field. Skip entries where `ssid == 'unconfigured'`.
