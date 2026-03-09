# status/lan – networks

<!-- path: status/lan/networks -->
<!-- type: status -->

[status](../) / [lan](../lan.md) / networks

---

Network name to network object (depth 3). Returned as `status/lan` → `networks`.

### Structure

**networks.{name}**

| Field | Type | Description |
|-------|------|-------------|
| `info` | object | See sub-table |
| `devices` | array | See sub-table |

**networks.{name}.info**

| Field | Type | Description |
|-------|------|-------------|
| `uid` | string | Network UID |
| `type` | string | Network type |
| `name` | string | Network name |
| `ip_address` | string | Network IP |
| `netmask` | string | Netmask |
| `broadcast` | string | Broadcast |
| `hostname` | string | Hostname |
| `ip_addresses` | array | IP addresses |
| `ip6_addresses` | array | IPv6 addresses |

**networks.{name}.devices[]**

| Field | Type | Description |
|-------|------|-------------|
| `uid` | string | Device UID |
| `type` | string | Device type |
| `iface` | string | Interface |
| `iface6` | string | IPv6 interface |
| `link_type` | string | Link type |
| `link_arptype` | string | Link ARP type |
| `link_base` | string\|null | Link base |
| `state` | string | Link state (optional) |
