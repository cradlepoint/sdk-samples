# Client Usage and QoS

## Client Usage Tracking

### API: status/client_usage

Returns per-client bandwidth statistics when client usage monitoring is enabled.

**Fields:**
- `enabled` (boolean) - Client usage monitoring status
- `stats` (array) - Per-client statistics

**stats[] fields:**
- `mac` (string) - Client MAC address
- `ip` (string) - Client IP address
- `name` (string) - Client name
- `network` (string) - Network name (e.g., "Primary LAN")
- `type` (string) - Client type
- `ssid` (string) - SSID (for wireless clients)
- `up_bytes` (integer) - Total bytes uploaded
- `down_bytes` (integer) - Total bytes downloaded
- `up_packets` (integer) - Total packets uploaded
- `down_packets` (integer) - Total packets downloaded
- `up_delta` (integer) - Upload delta since last poll
- `down_delta` (integer) - Download delta since last poll
- `last_time` (number) - Last activity timestamp
- `first_time` (number) - First seen timestamp
- `connect_time` (number) - Connection time

### Example

```python
import cp

data = cp.get('status/client_usage')
if data and data.get('enabled'):
    for client in data.get('stats', []):
        mac = client.get('mac')
        total_mb = (client.get('up_bytes', 0) + client.get('down_bytes', 0)) / 1024 / 1024
        cp.log(f"Client {mac}: {total_mb:.2f} MB used")
```

### Important Notes

- Requires client usage monitoring to be enabled in router settings
- Usage counters reset on router reboot
- Counters are cumulative since router boot or client first connection
- `status/lan/clients` does NOT have bandwidth data - only MAC and IP

## QoS Configuration

### API: config/qos

QoS has two main components: **queues** and **rules**.

**CRITICAL: QoS rules do NOT support MAC address matching** - only IP addresses.

### Structure

```python
qos = cp.get('config/qos')
# Returns: {'enabled': bool, 'queues': [...], 'rules': [...]}
```

### Queues

Define bandwidth limits. Rules reference queues by name.

```python
queue = {
    'name': 'Queue-512k',
    'dlenabled': True,
    'download_bw': 512,      # kbps
    'ulenabled': True,
    'upload_bw': 512,        # kbps
    'pri': 3,
    'downpri': 3,
    'dlsharing': False,
    'ulsharing': False,
    'download': 0,
    'upload': 0
}
```

### Rules

Match traffic and assign to queues. Use `lipaddr`/`lmask` for IP matching.

**Required fields:**
```python
rule = {
    'enabled': True,
    'name': 'Client-192.168.1.100',
    'ip_version': 'ip4',
    'lipaddr': '192.168.1.100',      # Local IP
    'lmask': '255.255.255.255',      # /32 for single IP
    'lneg': False,
    'lport_start': None,
    'lport_end': None,
    'rneg': False,
    'rport_start': None,
    'rport_end': None,
    'protocol': 'tcp/udp',
    'dscp_neg': False,
    'app_set_uuid': '',
    'queue': 'Queue-512k',           # Must match queue name
    'match_pri': 10
}
```

### Complete Example

```python
import cp

# Get current QoS config
qos = cp.get('config/qos') or {}
qos['enabled'] = True

# Create queue
queues = qos.get('queues', [])
queues.append({
    'name': 'Throttle-10M',
    'ulenabled': True,
    'dlenabled': True,
    'upload_bw': 10000,
    'download_bw': 10000,
    'pri': 3,
    'downpri': 3,
    'ulsharing': False,
    'dlsharing': False,
    'upload': 0,
    'download': 0
})
qos['queues'] = queues

# Create rule for client IP
rules = qos.get('rules', [])
rules.append({
    'enabled': True,
    'name': 'Client-192.168.1.100',
    'ip_version': 'ip4',
    'lipaddr': '192.168.1.100',
    'lmask': '255.255.255.255',
    'lneg': False,
    'lport_start': None,
    'lport_end': None,
    'rneg': False,
    'rport_start': None,
    'rport_end': None,
    'protocol': 'tcp/udp',
    'dscp_neg': False,
    'app_set_uuid': '',
    'queue': 'Throttle-10M',
    'match_pri': 10
})
qos['rules'] = rules

# Apply config
result = cp.put('config/qos', qos)
if result:
    cp.log('QoS updated successfully')
else:
    cp.log('ERROR: QoS update failed')
```

### Important Notes

- **MUST update entire config/qos object** - cannot update rules/queues separately
- **Verify cp.put() result** - returns True on success, False/None on failure
- **Use lipaddr for /32 rules** - set lmask to 255.255.255.255 for single IP
- **Queue must exist before rule** - create queue first, then reference by name
- **NO MAC address support** - use IP addresses only
