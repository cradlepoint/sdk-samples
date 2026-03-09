# status/firewall

<!-- path: status/firewall -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / firewall

---

Firewall/conntrack status: state timeouts, connection tracking, marks.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `state_timeouts` | object | See sub-table |
| `conntrack` | array | See [firewall/conntrack.md](firewall/conntrack.md) |
| `marks` | object | Mark name → hex string |
| `hitcounter` | array | See [firewall/hitcounter.md](firewall/hitcounter.md) |
| `npt` | object | See sub-table |
| `changenat` | array | NAT'd IP strings |
| `changezone` | array | Zone config UUIDs |
| `span` | object | SPAN/mirror state |

**state_timeouts**

| Field | Type | Description |
|-------|------|-------------|
| `state_entry_count` | number | Current conntrack entries |
| `state_entry_limit` | number | Conntrack limit |

**npt**

| Field | Type | Description |
|-------|------|-------------|
| `delegated_prefixes` | array | Delegated prefixes |
| `reserved_addresses` | array | Reserved addresses |

### SDK Example
```python
import cp
fw = cp.get('status/firewall')
if fw:
    to = fw.get('state_timeouts', {})
    cp.log(f'Conntrack: {to.get("state_entry_count")}/{to.get("state_entry_limit")}')
```

### REST
```
GET /api/status/firewall
```

### Breakout docs (in firewall/)
- [firewall/conntrack.md](firewall/conntrack.md) – conntrack[] (20+ fields per entry)
- [firewall/hitcounter.md](firewall/hitcounter.md) – hitcounter[] and rules[] (10+ fields)
