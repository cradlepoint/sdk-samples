# status/ecm – event_triggers

<!-- path: status/ecm/event_triggers -->
<!-- type: status -->

[status](../) / [ecm](../ecm.md) / event_triggers

---

Event trigger entries (13 fields each). Returned as `status/ecm` → `event_triggers`.

### event_triggers[] fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Trigger ID |
| `system` | string | System |
| `task_system` | string | Task system |
| `task_command` | string | Task command |
| `name` | string | Trigger name |
| `post_count` | number | Post count |
| `post_sent_ts` | number | Post sent timestamp |
| `post_ackd_ts` | number | Post acknowledged timestamp |
| `post_bytes` | number | Post bytes |
| `post_usage` | number | Post usage |
| `post_total_bytes` | number | Total post bytes |
| `post_total_usage` | number | Total post usage |
| `task_duration` | number | Task duration |
