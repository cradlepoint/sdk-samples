# status/wan/swans

<!-- path: status/wan/swans -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / swans

---

SWANS (Smart WAN Selection) status: priority, history, and data usage by WAN device. Used when multiple WANs are available and SWANS is configured.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `cm` | object | Connection manager, see sub-table |
| `history` | array | Selection history, see sub-table |
| `dataused` | object | Data usage, see sub-table |

**cm**

| Field | Type | Description |
|-------|------|-------------|
| `priority` | array | Device IDs in SWANS priority order (highest first) |

**history[]**

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | number | Epoch timestamp |
| `upd_status` | array | Per-device criteria, see sub-table |

**history[].upd_status[]**

| Field | Type | Description |
|-------|------|-------------|
| `wandev` | string | Device ID |
| `criteria` | object | See sub-table |

**dataused**

| Field | Type | Description |
|-------|------|-------------|
| `wandevs` | object | See sub-table |
| `updaters` | object | See sub-table |

**dataused.wandevs**

| Field | Type | Description |
|-------|------|-------------|
| *(key)* | string | WAN device ID |
| *(value)* | number | Bytes used |

**dataused.updaters**

| Field | Type | Description |
|-------|------|-------------|
| *(varies)* | * | Data updaters |

**history[].upd_status[].criteria**

| Field | Type | Description |
|-------|------|-------------|
| `CMPriority` | number | Priority value |
| *(varies)* | * | Other criteria |

### SDK Example
```python
import cp
swans = cp.get('status/wan/swans')
if swans:
    priority = swans.get('cm', {}).get('priority', [])
    cp.log(f'SWANS priority: {priority}')
    for h in swans.get('history', []):
        for u in h.get('upd_status', []):
            cp.log(f"  {u['wandev']}: CMPriority={u.get('criteria', {}).get('CMPriority')}")
```

### REST
```
GET /api/status/wan/swans
```

### Example Response
```json
{
  "success": true,
  "data": {
    "cm": {
      "priority": ["mdm-41949674", "mdm-41a3d8b1"]
    },
    "history": [
      {
        "epoch": 1772313919,
        "upd_status": [
          {"wandev": "mdm-41a3d8b1", "criteria": {"CMPriority": 2.7000231251}},
          {"wandev": "mdm-41949674", "criteria": {"CMPriority": 2.600023125}}
        ]
      }
    ],
    "dataused": {"wandevs": {}, "updaters": {}}
  }
}
```
