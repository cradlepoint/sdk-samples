# status/vpn – service

<!-- path: status/vpn/service -->
<!-- type: status -->

[status](../) / [vpn](../vpn.md) / service

---

strongSwan service state (10+ fields, depth 3). Returned as `status/vpn` → `service`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | STARTED, etc. |
| `conns` | array | Active connection configs |
| `version` | object | See sub-table |
| `stats` | object | See sub-table |
| `sas` | array | Security associations |
| `cfgs` | object | VICI configs (vici_cfg) |
| `certs` | object | VICI certificates |
| `policies` | object | VICI policies |
| `pools` | object | VICI pools |
| `retransmission_timeout` | number | Retransmission timeout |

**service.version**

| Field | Type | Description |
|-------|------|-------------|
| `daemon` | string | Daemon name |
| `version` | string | Version |
| `sysname` | string | System name |
| `release` | string | Release |
| `machine` | string | Machine |

**service.stats**

| Field | Type | Description |
|-------|------|-------------|
| `uptime` | object | `{running, since}` |
| `workers` | object | `{total, idle, active}` |
| `queues` | object | Queue stats (varies) |
| `scheduled` | string | Scheduled |
| `ikesas` | object | `{total, half-open}` |
| `plugins` | object | Plugin info (varies) |

**service.cfgs.vici_cfg** – Connection ID → VICI config array (varies)

**service.conns[]** – Connection config (local_addrs, remote_addrs, version, local, remote, children, etc.)
