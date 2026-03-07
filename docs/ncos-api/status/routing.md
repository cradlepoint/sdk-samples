# status/routing

<!-- path: status/routing -->
<!-- type: status -->
<!-- response: object -->

[status](../) / routing

---

Routing table and policy.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `table` | object | Per-table arrays (main, local, wan, vpn, etc.), see sub-table |
| `policy` | array | Policy entries, see sub-table |
| `static` | array | See sub-table |
| `cli` | object | See sub-table |
| `policysvc` | array | See sub-table |
| `changewans` | array | See sub-table |
| `static_multicast` | array | See sub-table |
| `truncated-tables` | array | See sub-table |

**table.{name}[] (route entry)**

| Field | Type | Description |
|-------|------|-------------|
| `ip_address` | string | Route destination |
| `netmask` | string | Netmask |
| `gateway` | string\|null | Gateway (null for connected) |
| `dev` | string\|null | Interface/device |
| `proto` | string | kernel, static |
| `metric` | integer | Route metric |

**policy[]**

| Field | Type | Description |
|-------|------|-------------|
| `priority` | number | Priority |
| `action` | string | Action |
| `table` | string | Table |
| `goto` | number | Goto |
| `src` | string | Source |
| `dst` | string | Destination |
| `in_dev` | string | Input device |
| `out_dev` | string | Output device |
| `mark` | number | Mark |
| `mask` | number | Mask |

**static[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Static route entry (same structure as table entries) |

**policysvc[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Policy service entry |

**changewans[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | WAN change tracking entry |

**static_multicast[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Static multicast route entry |

**truncated-tables[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Table name truncated |

**cli**

| Field | Type | Description |
|-------|------|-------------|
| `route` | string | Route CLI output |
| `rtpolicy_v4` | string | IPv4 policy CLI |
| `rtpolicy_v6` | string | IPv6 policy CLI |
| `arpdump` | string | ARP dump CLI |

### SDK Example
```python
import cp
routing = cp.get('status/routing')
if routing:
    main = routing.get('table', {}).get('main', [])
    for r in main:
        cp.log(f'{r.get("ip_address")}/{r.get("netmask")} via {r.get("gateway")} dev {r.get("dev")}')
```

### REST
```
GET /api/status/routing
```
