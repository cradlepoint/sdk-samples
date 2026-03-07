# status/nhrp

<!-- path: status/nhrp -->
<!-- type: status -->
<!-- response: object -->

[status](../) / nhrp

---

NHRP (Next Hop Resolution Protocol) mappings. **Empty when no DMVPN.**

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `mappings` | array | See sub-table |

**mappings[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | NHRP mapping entry (nbma, protocol address, etc.) |

See [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md) - configure DMVPN/NHRP.
