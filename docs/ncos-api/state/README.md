# state/ - NCOS State API

<!-- path: state -->
<!-- type: state -->

Runtime state: app registry, license, admin diagnostics, and other internal state. **Mostly read-only.** Primarily for diagnostics and internal use.

[NCOS API Documentation](../) / state

---

## Overview

| Operation | REST | SDK |
|-----------|------|-----|
| Read | `GET /api/state/{path}` | `cp.get('state/{path}')` |

**Note:** The api_specification marks state as "Internal use only - Should not be used by applications." Prefer [status/](../status/README.md) for application-visible runtime data. Use state/ for diagnostics, debugging, or when status/ does not provide the needed information.

## Top-Level Branches

| Path | Description |
|------|-------------|
| [state/system](system.md) | admin, apps, dyndns, license, netperf, overlay |
| [state/security](security.md) | IPS file state |
| [state/wan](wan.md) | Per-device auto_apn state |
| state/alerts | Alerts state |

## Key Subtrees

### state/system

| Field | Description |
|-------|-------------|
| `admin` | filesystem mount stats, reboot counts, ssh_host_key |
| `apps` | Installed SDK apps with files, hashes, metadata |
| `dyndns` | status (e.g. badauth) |
| `license` | had (UUIDs), ever_base_licensed, keys |
| `netperf` | run_count |
| `overlay` | Overlay state |

### state/system/admin

| Field | Type | Description |
|-------|------|-------------|
| `filesystem.mount_failure_count` | number | Mount failures |
| `filesystem.umount_failure_count` | number | Umount failures |
| `reboot_count.power_reset` | number | Power reset count |
| `reboot_count.system_reset` | number | System reset count |
| `reboot_count.watchdog_reset` | number | Watchdog reset count |
| `ssh_host_key` | string | SSH host key |

### state/system/apps

Array of `{app: {...}, _id_: uuid}`. Each app includes:
- uuid, name, date, restart, reboot, auto_start
- version_major, version_minor, version_patch
- files: [{name, hash}, ...]

### state/wan/devices

Array of `{id: device_id, auto_apn: {state, index, plmn, mode, iccid}}`.

## Access

```bash
GET /api/state/
GET /api/state/system
GET /api/state/system/apps
```

```python
import cp
apps = cp.get('state/system/apps')
admin = cp.get('state/system/admin')
```

## Related

- [status/](../status/README.md) - Preferred for application use
- [control/](../control/README.md) - Actions and commands
