# status/fw_info

<!-- path: status/fw_info -->
<!-- type: status -->
<!-- response: object -->

[status](../) / fw_info

---

Firmware version and upgrade status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `major_version` | integer | Major version |
| `minor_version` | integer | Minor version |
| `patch_version` | integer | Patch version |
| `build_date` | string | Build date |
| `build_version` | string | Git/build hash |
| `build_type` | string | RELEASE, etc. |
| `fw_update_available` | boolean | Update available |
| `upgrade_major_version` | integer | Available upgrade major |
| `upgrade_minor_version` | integer | Available upgrade minor |
| `upgrade_patch_version` | integer | Available upgrade patch |
| `sign_cert_types` | string | Cert types (e.g. "ROOTCA RELEASE") |
| `fw_release_tag` | string | Release tag (e.g. "FR2") |
| `manufacturing_upgrade` | boolean | Manufacturing upgrade flag |
| `multi_images` | array | See sub-table |

**multi_images[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Multi-image info entry |

### SDK Example
```python
import cp
fw = cp.get('status/fw_info')
if fw:
    v = fw.get('major_version', 0), fw.get('minor_version', 0), fw.get('patch_version', 0)
    cp.log(f'NCOS {v[0]}.{v[1]}.{v[2]}')
```

### REST
```
GET /api/status/fw_info
```
