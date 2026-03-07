# status/certmgmt

<!-- path: status/certmgmt -->
<!-- type: status -->
<!-- response: object -->

[status](../) / certmgmt

---

Certificate management status. **Minimal when idle.**

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `view` | array | See sub-table |
| `ca_fingerprints` | array | See sub-table |

**view[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Certificate view entry (name, fingerprint, expiry, etc.) |

**ca_fingerprints[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | CA fingerprint entry |

See [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md) - add certs/CA to populate.
