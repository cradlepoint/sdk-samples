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
