# state/security

<!-- path: state/security -->
<!-- type: state -->
<!-- response: object -->

[state](../) / security

---

Security state: IPS (Intrusion Prevention) file versions.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ips` | object | IPS state |
| `ips.current_file_v3` | string | Current rules file (e.g. rules_1_415.tgz) |
| `ips.last_updated` | number | Last update timestamp |
| `ips.prev_file_v3` | string | Previous rules file |

### SDK Example
```python
import cp
sec = cp.get('state/security')
ips = sec.get('ips', {})
cp.log(f"IPS: {ips.get('current_file_v3')} updated {ips.get('last_updated')}")
```

### REST
```
GET /api/state/security
```

### Related
- [control/security](../control/README.md) - IPS action, update
- [status/security](../status/security.md) - Security status
