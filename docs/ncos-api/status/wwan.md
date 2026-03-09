# status/wwan

<!-- path: status/wwan -->
<!-- type: status -->
<!-- response: object -->

[status](../) / wwan

---

WiFi-as-WAN (WWAN) device status. **Empty when no WWAN devices.**

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `devices` | array | See sub-table |

**devices[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | WWAN device object (device_id, status, etc.) |

See [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md) - add WiFi-as-WAN to populate.
