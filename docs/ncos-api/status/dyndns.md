# status/dyndns

<!-- path: status/dyndns -->
<!-- type: status -->
<!-- response: string -->

[status](../) / dyndns

---

Dynamic DNS status. String response indicating state or error.

### Response Type
`string`

### Common Values
- `good` - Update succeeded
- `nochg` - No change needed
- `badauth` - Auth failed (username/password)
- `notcfg` - Not configured
- Other provider-specific codes

### SDK Example
```python
import cp
dyndns = cp.get('status/dyndns')
if dyndns:
    cp.log(f'Dynamic DNS: {dyndns}')
```

### REST
```
GET /api/status/dyndns
```

### Example Response
```json
{"success": true, "data": "badauth"}
```
