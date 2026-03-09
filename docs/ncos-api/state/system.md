# state/system

<!-- path: state/system -->
<!-- type: state -->
<!-- response: object -->

[state](../) / system

---

System state: admin diagnostics, installed apps, license, dyndns.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `admin` | object | See sub-table |
| `apps` | array | Installed SDK apps, see sub-table |
| `dyndns` | object | Dyndns status |
| `license` | object | See sub-table |
| `netperf` | object | Netperf run count |
| `overlay` | object | Overlay state |

**admin**

| Field | Type | Description |
|-------|------|-------------|
| `filesystem` | object | mount_failure_count, umount_failure_count |
| `reboot_count` | object | power_reset, system_reset, watchdog_reset |
| `ssh_host_key` | string | SSH host key |

**apps[]**

| Field | Type | Description |
|-------|------|-------------|
| `app` | object | App metadata and files |
| `app.uuid` | string | App UUID |
| `app.name` | string | App name |
| `app.date` | string | Install date |
| `app.restart` | boolean | Restart on change |
| `app.reboot` | boolean | Reboot on change |
| `app.auto_start` | boolean | Auto start |
| `app.version_major` | number | Version |
| `app.files` | array | {name, hash} per file |
| `_id_` | string | App UUID |

**dyndns**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | good, badauth, nochg, etc. |

**license**

| Field | Type | Description |
|-------|------|-------------|
| `had` | array | Past license UUIDs |
| `ever_base_licensed` | boolean | Ever had base license |
| `keys` | object | UUID → enabled |

### SDK Example
```python
import cp
# List installed apps
apps = cp.get('state/system/apps')
for entry in apps or []:
    a = entry.get('app', {})
    cp.log(f"App: {a.get('name')} {a.get('uuid')}")
# Reboot counts
admin = cp.get('state/system/admin')
rc = admin.get('reboot_count', {})
cp.log(f"Resets: power={rc.get('power_reset')} system={rc.get('system_reset')}")
```

### REST
```
GET /api/state/system
GET /api/state/system/apps
GET /api/state/system/admin
```

### Related
- [status/system](../status/system.md) - System status
- [status/product_info](../status/product_info.md) - Product info
