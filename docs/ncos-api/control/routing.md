# control/routing

<!-- path: control/routing -->
<!-- type: control -->
<!-- response: object -->

[control](../) / routing

---

Routing control: add/del static routes, route tables, suppression.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `static` | object | Static route control |
| `static.route` | object | add, del |
| `static.table` | object | add, del |
| `static.refresh` | boolean | Refresh routes |
| `suppression` | object | add, del |

**static.route.add**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID |
| `destination` | string | IP or netcidr |
| `gateway` | string | Gateway IP or netcidr |
| `interface` | string | Network interface |
| `table` | string | Table name |
| `metric` | string | Route priority |

**static.route.del**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | ID to remove |

**static.table.add**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID |
| `family` | array | ipv4, ipv6 |
| `priority` | string | 0–50000 |
| `ingress_interface` | array | any, wan, ecm, etc. |
| `source` | array | IP or netcidr |

**suppression.add**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `src` | array | Source IPs/netcidrs |
| `dest` | array | Dest IPs/netcidrs |
| `exception` | string | Exception dest |
