# status/system – debug_info

<!-- path: status/system/debug_info -->
<!-- type: status -->

[status](../) / [system](../system.md) / debug_info

---

Debug/ECM info (depth 3). Returned as `status/system` → `debug_info`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ecm` | object | See sub-table |
| `module` | object | See sub-table |

**debug_info.ecm**

| Field | Type | Description |
|-------|------|-------------|
| `ecm_nss_ipv4` | object | See sub-table |
| `ecm_nss_ipv6` | object | See sub-table |
| `ecm_db` | object | See sub-table |

**debug_info.ecm.ecm_nss_ipv4 / ecm_nss_ipv6**

| Field | Type | Description |
|-------|------|-------------|
| `accelerated_count` | string | Accelerated count |
| `tcp_accelerated_count` | string | TCP accelerated count |
| `udp_accelerated_count` | string | UDP accelerated count |

**debug_info.ecm.ecm_db**

| Field | Type | Description |
|-------|------|-------------|
| `connection_count` | string | Connection count |

**debug_info.module**

| Field | Type | Description |
|-------|------|-------------|
| `tdts` | object | See sub-table |

**debug_info.module.tdts**

| Field | Type | Description |
|-------|------|-------------|
| `initstate` | string | Init state |
