# status/wlan

<!-- path: status/wlan -->
<!-- type: status -->
<!-- response: object -->

[status](../) / wlan

---

WiFi radio status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | On, Off, etc. |
| `debug` | object | See sub-table |
| `radio` | array | Per-radio objects, see sub-table |
| `region` | object | See sub-table |
| `events` | object | See sub-table |
| `trace` | array | See sub-table |

**debug**

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | Debug state |

**radio[]**

| Field | Type | Description |
|-------|------|-------------|
| `channel` | number | Current channel |
| `band` | string | 2.4 GHz, 5 GHz |
| `channel_list` | array | Available channels |
| `channel_locked` | boolean | Channel locked |
| `bss` | array | See sub-table |
| `clients` | array | Per-client objects |
| `txpower` | number | TX power |

**radio[].bss[]**

| Field | Type | Description |
|-------|------|-------------|
| `bssid` | string | BSSID |
| `ssid` | string | SSID (optional) |
| `clients` | array | Associated clients (optional) |
| *(varies)* | * | Other BSS fields |

**radio[].clients[]**

| Field | Type | Description |
|-------|------|-------------|
| `mac` | string | Client MAC |
| `rssi0` | number | RSSI antenna 0 |
| `rssi1` | number | RSSI antenna 1 |
| `rxrate` | number | Receive rate |
| `txrate` | number | Transmit rate |
| `aid` | number | Association ID |

**region**

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Version |
| `country_code` | string | Country code |
| `regions_supported` | array | Supported regions |

**events**

| Field | Type | Description |
|-------|------|-------------|
| `associate` | array | MAC addresses (associated) |
| `disassociate` | array | MAC addresses (disassociated) |
| `timeout` | array | MAC addresses (timeout) |

**trace[]** (array of mixed values per entry)

| Index | Type | Description |
|-------|------|-------------|
| 0 | number | Timestamp |
| 1 | string | Address |
| 2 | number | Code |
| 3 | string | Command/args |

### SDK Example
```python
import cp
wlan = cp.get('status/wlan')
if wlan:
    cp.log(f'WiFi: {wlan.get("state")} radios={len(wlan.get("radio", []))}')
```

### REST
```
GET /api/status/wlan
```
