# status/ecm – last_patch

<!-- path: status/ecm/last_patch -->
<!-- type: status -->

[status](../) / [ecm](../ecm.md) / last_patch

---

Last patch config (depth 3). Returned as `status/ecm` → `last_patch`.

### last_patch[] structure

| Field | Type | Description |
|-------|------|-------------|
| `config` | object | See sub-table |
| `diff` | * | Diff data |

**last_patch[].config**

| Field | Type | Description |
|-------|------|-------------|
| `ecm` | object | See sub-table |
| *(varies)* | * | Other config sections |

**last_patch[].config.ecm**

| Field | Type | Description |
|-------|------|-------------|
| `config_version` | number | Config version |
