# config/ - Configuration API

<!-- path: config -->
<!-- type: config -->

Configuration tree. **Read/write** via GET, PUT, POST. Persisted to NVRAM.

[NCOS API Documentation](../) / config

---

## Overview

| Operation | REST | SDK |
|-----------|------|-----|
| Read | `GET /api/config/{path}` | `cp.get('config/{path}')` |
| Write | `PUT /api/config/{path}` | `cp.put('config/{path}', value)` |
| Create (arrays) | `POST /api/config/{path}` | `cp.post('config/{path}', value)` |
| Delete | `DELETE /api/config/{path}/{_id_}` | — |

### REST API Data Format

**CRITICAL: REST writes use form-encoded `data=` parameter, NOT JSON body.**

```bash
# POST (create) - form data with JSON value
curl -k -u admin:pass -X POST "https://ROUTER/api/config/{path}/" \
  -d 'data={"name":"field","value":"val"}'

# PUT (update) - form data with JSON value
curl -k -u admin:pass -X PUT "https://ROUTER/api/config/{path}/{_id_}/" \
  -d 'data={"name":"field","value":"val"}'

# DELETE
curl -k -u admin:pass -X DELETE "https://ROUTER/api/config/{path}/{_id_}"
```

**Do NOT use `-H "Content-Type: application/json"` with `-d '{...}'` — the router expects `data=` form encoding.**

### Array Indexing

Many config arrays contain objects with an `_id_` field (UUID). You can access array elements by:
- **Numeric index**: `config/wan/rules2/0`
- **ID value**: `config/wan/rules2/{_id_}`

Both methods return the same object. Using `_id_` is preferred when you have the UUID from another API call.

```python
import cp
# By index
rule = cp.get('config/wan/rules2/0')
# By _id_
rule_id = 'a1b2c3d4-...'
rule = cp.get(f'config/wan/rules2/{rule_id}')
```

## Path Index

- **[PATHS.md](PATHS.md)** - Full list of config paths (generated from DTD)
- **[wan-rules2.md](wan-rules2.md)** - WAN rules configuration (device matching, disabled field)

## Schema (DTD)

The config tree schema is defined in **NCOS DTD** JSON files, one per router model and firmware version. Types, defaults, min/max, and structure come from the DTD. Different models have different schemas based on their hardware (ports, radios, modems, etc.).

| File | Model | NCOS Version | Description |
|------|-------|--------------|-------------|
| [dtd/E3000-NCOS-7.25.101.json](dtd/E3000-NCOS-7.25.101.json) | E3000 | 7.25.101 | 10 ethernet ports (4 PoE), enterprise branch router |

See **[dtd/README.md](dtd/README.md)** for naming conventions, how to add DTDs from other models, and what varies between models.

**Note:** The status tree is *not* defined in the DTD; it is runtime-only. See [status/](../status/README.md).

## Regenerating the Path Index

When the DTD is updated (e.g. new NCOS version), regenerate PATHS.md:

```bash
python3 generate_config_paths.py
```

(Run from `NCOS API Documentation/` or pass `--dtd` and `--output`.)

## Related

- [status/](../status/README.md) - Status API (read-only)
- [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md) - Features that affect both config and status
