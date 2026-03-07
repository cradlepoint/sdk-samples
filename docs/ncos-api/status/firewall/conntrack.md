# status/firewall – conntrack

<!-- path: status/firewall/conntrack -->
<!-- type: status -->

[status](../) / [firewall](../firewall.md) / conntrack

---

Connection tracking entries (20+ fields each). Returned as `status/firewall` → `conntrack`.

### conntrack[] fields

| Field | Type | Description |
|-------|------|-------------|
| `family` | number | Address family |
| `proto` | number | Protocol (6=tcp) |
| `timeout` | number | Timeout seconds |
| `mark` | string | Packet mark |
| `mark_mask` | number | Mark mask |
| `use` | number | Use count |
| `id` | number | Connection ID |
| `tcp_state` | string | TIME_WAIT, ESTABLISHED, etc. |
| `status` | string | seen_reply, assured, etc. |
| `orig_src` | string | Origin source IP |
| `orig_src_port` | number | Origin source port |
| `orig_dst` | string | Origin dest IP |
| `orig_dst_port` | number | Origin dest port |
| `orig_packets` | number | Origin packets |
| `orig_bytes` | number | Origin bytes |
| `reply_src` | string | Reply source IP |
| `reply_src_port` | number | Reply source port |
| `reply_dst` | string | Reply dest IP |
| `reply_dst_port` | number | Reply dest port |
| `reply_packets` | number | Reply packets |
| `reply_bytes` | number | Reply bytes |
| *(varies)* | * | orig_icmp_*, reply_icmp_*, cat_id, app_id, dscp |
