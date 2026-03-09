# status/wan/steering

<!-- path: status/wan/steering -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / steering

---

Traffic steering status: events, stats, rules, and intents. Used when affinity/steering rules bind traffic to specific WAN devices.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `events` | object | See sub-table |
| `stats` | object | See sub-table |
| `perf` | object | See sub-table |
| `rules` | array | See sub-table |
| `intents` | object | See sub-table |

**intents**

| Field | Type | Description |
|-------|------|-------------|
| *(key)* | string | Intent identifier |
| *(value)* | * | Intent data |

**events**

| Field | Type | Description |
|-------|------|-------------|
| `began_capture` | number | Capture start time |
| `total_perf_events` | number | Total performance events |
| `steering_events` | array | See sub-table |
| `event_overflow` | boolean | Overflow flag |

**stats**

| Field | Type | Description |
|-------|------|-------------|
| `began_capture` | number | Capture start time |
| `flows_truncated` | boolean | Flows truncated |
| `rules` | array | See sub-table |

**perf**

| Field | Type | Description |
|-------|------|-------------|
| `event_overflow` | boolean | Event overflow flag |

**rules[] (top-level and stats.rules)**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Steering rule or rule entry |

**events.steering_events[]**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Steering event entry |

### SDK Example
```python
import cp
steering = cp.get('status/wan/steering')
if steering:
    rules = steering.get('rules', [])
    intents = steering.get('intents', {})
    cp.log(f'Steering rules: {len(rules)}, intents: {len(intents)}')
```

### REST
```
GET /api/status/wan/steering
```

### Example Response
```json
{
  "success": true,
  "data": {
    "events": {"began_capture": 1772148824.45, "total_perf_events": 0, "event_overflow": false, "steering_events": []},
    "stats": {"began_capture": 1772148824.45, "flows_truncated": false, "rules": []},
    "perf": {"event_overflow": false},
    "rules": [],
    "intents": {}
  }
}
```
