# status/modem

<!-- path: status/modem -->
<!-- type: status -->
<!-- response: object -->

[status](../) / modem

---

Modem upgrade audit trail.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `audit` | object | See sub-table |

**audit**

| Field | Type | Description |
|-------|------|-------------|
| `Version` | number | Audit format version |
| `Port` | object | Port ID → port object, see sub-table |

**audit.Port.{id}**

| Field | Type | Description |
|-------|------|-------------|
| `total_upgrades` | number | Total upgrades |
| `upgrades` | array | See sub-table |

**audit.Port.{id}.upgrades[]**

| Field | Type | Description |
|-------|------|-------------|
| `TO` | string | To version |
| `FROM` | string | From version |
| `IMEI` | string | IMEI |
| `MODEL` | string | Model |
| `MFG_MODEL` | string | Manufacturer model |
| `STATUS` | string | Status |
| `TIME` | string | Time |

### SDK Example
```python
import cp
modem = cp.get('status/modem')
if modem:
    audit = modem.get('audit', {})
    cp.log(f'Modem audit: {list(audit.keys())}')
```

### REST
```
GET /api/status/modem
```
