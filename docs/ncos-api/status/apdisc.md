# status/apdisc

<!-- path: status/apdisc -->
<!-- type: status -->
<!-- response: object -->

[status](../) / apdisc

---

AP discovery. **Minimal when not configured.**

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `neighbors` | object | See sub-table |

**neighbors**

| Field | Type | Description |
|-------|------|-------------|
| *(key)* | string | Neighbor identifier |
| *(value)* | object | See sub-table |

**neighbors.{id}**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Neighbor info |

See [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md) - enable AP discovery to populate.
