# status/system – sdk

<!-- path: status/system/sdk -->
<!-- type: status -->

[status](../) / [system](../system.md) / sdk

---

SDK service and apps. Returned as `status/system` → `sdk`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `service` | string | SDK service state |
| `summary` | string | Summary |
| `mode` | string | Mode |
| `apps` | array | See sub-table |

**sdk.apps[]**

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | string | App config ID |
| `app` | object | See sub-table |
| `state` | string | started, etc. |
| `summary` | string | Status summary |

**sdk.apps[].app**

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | App UUID |
| `name` | string | App name |
| `date` | string | Install/update date |
| `restart` | boolean | Restart allowed |
| `reboot` | boolean | Reboot allowed |
| `auto_start` | boolean | Auto-start enabled |
| `notes` | string | Notes |
| `vendor` | string | Vendor |
| `version_major` | integer | Major version |
| `version_minor` | integer | Minor version |
| `version_patch` | integer | Patch version |
