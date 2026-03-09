# status/firewall – hitcounter

<!-- path: status/firewall/hitcounter -->
<!-- type: status -->

[status](../) / [firewall](../firewall.md) / hitcounter

---

Firewall rule hit counters. Returned as `status/firewall` → `hitcounter`.

### hitcounter[] fields

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | string | Rule config ID |
| `default_action` | string | allow, deny |
| `name` | string | Rule name |
| `packet_count` | number | Packet count |
| `bytes_count` | number | Bytes count |
| `rules` | array | See sub-table |

### hitcounter[].rules[] fields

| Field | Type | Description |
|-------|------|-------------|
| `pkt_count` | number | Packet count |
| `byte_count` | number | Byte count |
| `target_rule` | string | ACCEPT, DROP, etc. |
| `protocol` | string | all, tcp, udp, etc. |
| `option` | string | Option |
| `in_interface` | string | Input interface |
| `out_interface` | string | Output interface |
| `src_addr` | string | Source address |
| `dest_addr` | string | Dest address |
| `description` | string | Description |
| `ip_version` | string | IPv4, IPv6 |
