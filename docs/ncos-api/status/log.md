# status/log

<!-- path: status/log -->
<!-- type: status -->
<!-- response: array -->

[status](../) / log

---

System log entries. Array of `[timestamp, level, source, message, extra?]`.

### Fields (per array element)

| Index | Type | Description |
|-------|------|-------------|
| 0 | number | Timestamp |
| 1 | string | Level (info, warn, error, etc.) |
| 2 | string | Source |
| 3 | string | Message |
| 4 | * | Extra (optional) |

### SDK Example
```python
import cp
logs = cp.get('status/log')
if logs:
    for entry in logs[-5:]:
        ts, level, src, msg = entry[0], entry[1], entry[2], entry[3]
        cp.log(f'{ts} [{level}] {src}: {msg[:80]}')
```

### REST
```
GET /api/status/log
```
