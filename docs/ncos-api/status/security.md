# status/security

<!-- path: status/security -->
<!-- type: status -->
<!-- response: object -->

[status](../) / security

---

Security status.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `default_password` | object | See sub-table |
| `ips` | object | See sub-table |

**ips**

| Field | Type | Description |
|-------|------|-------------|
| `signature_version` | object | See sub-table |
| `engine_version` | object | See sub-table |
| `last_updated` | number | Last update timestamp |
| `sigIds` | object | Signature IDs by category, see sub-table |
| *(varies)* | * | Other IPS state |

**ips.signature_version**

| Field | Type | Description |
|-------|------|-------------|
| `major` | string | Major version |
| `minor` | string | Minor version |

**ips.engine_version**

| Field | Type | Description |
|-------|------|-------------|
| `major` | number | Major version |
| `minor` | number | Minor version |
| `rev` | number | Revision |

**ips.sigIds**

| Field | Type | Description |
|-------|------|-------------|
| `ips_categories` | object | Category ID → `{name}` |
| *(varies)* | * | Other signature data |

**default_password**

| Field | Type | Description |
|-------|------|-------------|
| `admin` | boolean | Admin password changed |
| `wifi` | boolean | WiFi password changed |

### SDK Example
```python
import cp
sec = cp.get('status/security')
if sec:
    dp = sec.get('default_password', {})
    cp.log(f'Security: admin_changed={dp.get("admin")}')
```

### REST
```
GET /api/status/security
```
