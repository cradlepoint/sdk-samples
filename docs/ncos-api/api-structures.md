# NCOS API Structures — Detailed Reference

Detailed API response structures, patterns, and gotchas. Referenced from `.kiro/steering/api-reference.md`.

## System

```python
data = cp.get('status/system')
# dict with cpu (fractions!), memory (bytes), uptime (seconds), temperature (C)
cpu_percent = (data.get('cpu', {}).get('user', 0) + data.get('cpu', {}).get('system', 0)) * 100
```

## Router Hostname

```python
hostname = cp.get('config/system/system_id')  # e.g., 'IBR1700-abc'
```

## LAN IP Address

```python
lans = cp.get('config/lan') or []
for lan in lans:
    if lan.get('ip_address'):
        server_ip = lan['ip_address']  # e.g., '192.168.0.1'
        break
```

## Disk

```python
data = cp.get('status/mount')
disk = data.get('disk_usage', {})  # {'total_bytes': int, 'free_bytes': int}
```

## WAN Devices

```python
data = cp.get('status/wan/devices')  # {'ethernet-wan': {...}, 'mdm-xxx': {...}}
# Each device has nested structure: device['info']['type'], device['diagnostics'], device['status']
# Check device type: device.get('info', {}).get('type') == 'mdm'
# CRITICAL: Each SIM slot is a separate mdm device (mdm-12345, mdm-67890)
# CRITICAL: SIM slot is in device['info']['sim'] ('sim1' or 'sim2')
# CRITICAL: Same physical modem = same device['info']['port'] (e.g., 'int1')
# PATTERN: Detect SIM failover by tracking primary_device's info.sim changing from 'sim1' to 'sim2'
# Modem diagnostics: device.get('diagnostics', {}) contains RSRP, RSRQ, SINR, RFBAND, CARRID, etc.
state = cp.get('status/wan/connection_state')  # 'connected' or 'disconnected' string
primary = cp.get('status/wan/primary_device')  # device name string like 'mdm-41949674'
```

## LAN Clients

```python
clients = cp.get('status/lan/clients')  # [{'ip_address': str, 'mac': str, 'hostname': str}, ...]
```

**CRITICAL: status/lan/clients does NOT have rx_bytes/tx_bytes — use status/client_usage for bandwidth data**

## Client Usage

```python
usage = cp.get('status/client_usage')  # {'enabled': bool, 'stats': [{'mac': str, 'ip': str, 'up_bytes': int, 'down_bytes': int, ...}]}
```

## Firewall Conntrack

```python
fw = cp.get('status/firewall')  # {'conntrack': [...], 'state_entry_count': int}
conntrack = fw.get('conntrack', [])
# [{'id': int, 'orig_src': str, 'orig_dst': str, 'orig_bytes': int, 'reply_bytes': int, 'tcp_state': str, ...}]
```

- Track by connection `id` field to avoid double-counting stale entries
- Connections persist in conntrack after traffic stops — check byte increments for activity
- Initialize global tracker with zero bytes, calculate deltas each cycle
- Filter out closing TCP states (TIME_WAIT, CLOSE_WAIT, FIN_WAIT*, LAST_ACK, CLOSING)
- Track by MAC address not IP when correlating with clients — IPs can change (DHCP renewal)
- Resolve all IPs for a domain — CDNs/load balancers use multiple IPs (use `socket.getaddrinfo` with `AF_INET` for IPv4 only)
- Pattern: Global conn tracker `{conn_id: {'tx': bytes, 'rx': bytes, 'last_seen': time}}`
- Pattern: Per-cycle deltas — `delta = current_bytes - tracker[conn_id]['bytes']`, then update tracker
- Pattern: Activity detection — only count as active when `delta > 0`, not just when connection exists

## DHCP Leases

```python
dhcpd = cp.get('status/dhcpd')  # {'leases': [{'ip_address': str, 'mac': str, 'hostname': str, 'network': str, 'ssid': str, ...}]}
```

## ARP Table

```python
arpdump = cp.get('status/routing/cli/arpdump')
# String with lines: "Type Interface State Link_Address IP_Address"
```

- Parse line by line, split by whitespace
- Only REACHABLE entries are active connections
- Check for IPv4 by testing if `:` NOT in IP (IPv6 has colons)
- Interface names have trailing digits (primarylan3) — strip with `re.sub(r'\d+$', '', interface)`
- Pattern: `parts = line.split(); if parts[0]=='ethernet' and parts[2]=='REACHABLE' and ':' not in parts[4]`

## LAN Networks

```python
info = cp.get('status/lan/networks/{interface}/info')  # {'name': str, 'vlan_id': int, ...}
```

- Interface name must NOT have trailing digit (use `primarylan` not `primarylan3`)
- Network `name` field is used to match firewall filter policies

## LAN Config

```python
lans = cp.get('config/lan')  # [{'_id_': str, 'name': str, 'ip_address': str, 'netmask': str, 'enabled': bool, ...}]
```

- Returns array of dicts, NOT dict keyed by path
- Each LAN has `name` field that matches filter policy names

## Firewall Filter Policies (ZFW)

```python
policies = cp.get('config/security/zfw/filter_policies')
# [{'_id_': str, 'name': str, 'default_action': str, 'rules': [...]}]
```

- Match policy by `name` field to network name from `status/lan/networks`
- Must get/put entire rules array — cannot update individual rules
- MAC filtering uses `src.mac` array: `[{'identity': 'aa:bb:cc:dd:ee:ff'}]`
- Pattern: Get rules, modify array, put back: `cp.put(f'config/security/zfw/filter_policies/{_id_}/rules', rules)`
- Rule structure:
  ```python
  {'action': 'deny'|'allow', 'name': str, 'priority': int, 'ip_version': 'ip4'|'ip6',
   'src': {'ip': [], 'mac': [{'identity': str}], 'port': []},
   'dst': {'ip': [], 'port': []}, 'protocols': [], 'app_sets': []}
  ```

## QoS

```python
qos = cp.get('config/qos')  # {'enabled': bool, 'queues': [...], 'rules': [...]}
```

- Must put entire qos object, cannot update rules/queues separately
- QoS rules use IP addresses only (lipaddr/lmask), NO MAC address support
- Pattern: Use prefixes to identify app-managed resources (e.g., `MyApp-` prefix for queue/rule names)
- Pattern: For per-client limits with shared queues, create queue per unique limit, not per client

## Router Logs

```python
# REST API: GET /api/status/log/
# Returns {"success": true, "data": [[timestamp, facility, level, message], ...]}
# timestamp is Unix epoch (seconds), message is the log text
```

- ALWAYS include timestamps when reading logs
- Convert timestamps to human-readable with `datetime.fromtimestamp(ts)`
- Filter by recency — after deploying, only look at logs with timestamps AFTER the deploy started
- Log entry format: `[timestamp, facility, level, message]` — index 0 = epoch, index 3 = message text

## Certificate Management

- Router can generate CA, server, and client X.509 certs via `control/certmgmt/ca`
- Use `cp.decrypt()` to retrieve encrypted private keys
- Router can export `.p12` (PKCS#12) files via REST: `GET /api/certexport?uuid={uuid}&passphrase={pw}&filetype=P12` (requires Basic Auth, not available via SDK `cp` module)
- For SDK apps needing `.p12` without admin creds, use pure-Python PKCS#12 encoding with PEM data from `cp.get()`/`cp.decrypt()`
- Router cert store has limited space — creating many certs can hit "exceeds config store storage limit". Reuse existing certs when possible
- Cert creation is async — after `cp.put('control/certmgmt/ca', {...})`, wait ~5 seconds before trying to find the cert
- Full docs: `docs/ncos-api/control/certmgmt.md`

## SSL/TLS Patterns

- Server SSL context: `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)` with `load_cert_chain()` and `load_verify_locations()`
- Client SSL context (self-signed): `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` with `check_hostname=False` and `verify_mode=ssl.CERT_NONE`
- Wrap sockets: Server: `ctx.wrap_socket(sock, server_side=True)`, Client: `ctx.wrap_socket(sock, server_hostname=host)`
- Non-blocking SSL: After wrapping, `sock.setblocking(False)` — handle `ssl.SSLWantReadError` and `ssl.SSLWantWriteError` in recv/send
