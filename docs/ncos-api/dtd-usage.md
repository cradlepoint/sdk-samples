# Using DTD to Verify API Structures

## DTD Endpoint

**ALWAYS check the DTD before writing config API code:**

```bash
curl -s -u admin:pass http://router/api/dtd/config/path | python3 -m json.tool
```

The DTD (Document Type Definition) shows:
- Exact field names and types
- Required vs optional fields
- Default values
- Min/max values for numbers
- Array max lengths
- Allowed options for select fields

## Example: QoS Configuration

### Check DTD First

```bash
curl -s -u admin:pass http://router/api/dtd/config/qos | python3 -m json.tool
```

Shows:
- `enabled` (boolean, default: false)
- `queues` (array, maxlength: 20)
- `rules` (array, maxlength: 20, default: [])

### QoS Rules DTD

From `/api/dtd/config/qos`, rules have these fields:
- `enabled` (boolean, default: true)
- `name` (string, maxlength: 32)
- `lipaddr` (ipv4_address, allowBlank: true) - Local IP
- `lmask` (ipv4_address, allowBlank: true) - Local mask
- `ripaddr` (ipv4_address, allowBlank: true) - Remote IP
- `rmask` (ipv4_address, allowBlank: true) - Remote mask
- `lport_start`, `lport_end` (u16, min: 1, allowBlank: true)
- `rport_start`, `rport_end` (u16, min: 1, allowBlank: true)
- `protocol` (select: tcp/udp, tcp, udp, icmp, any, default: tcp/udp)
- `queue` (string, maxlength: 32) - Queue name to assign
- `ip_version` (select: ip4, ip6, default: ip4)
- `match_pri` (u16, default: 0)

**NO MAC address fields exist** - only IP addresses

### QoS Queues DTD

- `name` (string, maxlength: 32)
- `dlenabled` (boolean, default: true)
- `download_bw` (u32, default: 0) - kbps
- `ulenabled` (boolean, default: true)
- `upload_bw` (u32, default: 0) - kbps
- `pri` (u8, 0-7, default: 3)
- `downpri` (u8, 0-7, default: 3)
- `dlsharing` (boolean, default: true)
- `ulsharing` (boolean, default: true)

## Correct QoS Configuration

```python
import cp

# Build complete structure
qos_data = {
    'enabled': True,
    'queues': [{
        'name': 'throttle_queue',
        'dlenabled': True,
        'download_bw': 512,
        'ulenabled': True,
        'upload_bw': 512,
        'pri': 1,
        'downpri': 1,
        'dlsharing': True,
        'ulsharing': True
    }],
    'rules': [{
        'enabled': True,
        'name': 'limit_client',
        'lipaddr': '192.168.1.100',
        'lmask': '255.255.255.255',
        'queue': 'throttle_queue'
    }]
}

# PUT entire structure
cp.put('config/qos', qos_data)
```

## Key Learnings

1. **Always check DTD first** - don't assume field names or types
2. **Use `/api/dtd/config/path`** to see exact structure
3. **Build fresh structures** - don't append to existing and PUT back
4. **Match DTD types exactly** - boolean not string, u32 not string
5. **QoS rules match by IP, not MAC** - use lipaddr/lmask fields
6. **Silent failures** - router may accept PUT but silently reject invalid rules
7. **Test after PUT** - always GET the config back to verify it was saved
8. **Check logs** - cp.put() returns status but router may still reject data
