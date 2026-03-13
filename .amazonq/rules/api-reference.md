# Cradlepoint NCOS API Reference

## CP Module

- Always `import cp` and use module-level functions when possible
- Never use EventingCSClient or CSClient classes
- **ALWAYS check @cp.py for helper functions before using direct API calls**
- **NEVER make up function names** - if you don't know what functions exist, read @cp.py first
- **cp.py helper functions are for simple use cases and may return minimal data (UIDs, tuples) rather than full objects** - for detailed data, prefer direct API calls
- **cp.get() returns data directly, NOT wrapped in {"success": true, "data": ...}** - the wrapper is only in raw HTTP API responses
- **ALWAYS use cp.get_appdata('field_name') with a field name** - never call without args to get all appdata
- **cp.get_appdata() without args returns a LIST of dicts, not a dict** - each item has 'name', 'value', '_id_'
- **cp.put_appdata(name, value) takes TWO arguments** - name and value as separate strings, NOT a dict
- **Appdata is stored in config, not status** - `config/system/sdk/appdata` (not status/system/sdk/appdata)
- Document all appdata fields in readme.md

## NCOS API Documentation

- **Full API docs**: `docs/ncos-api/` - status, config, control, and state APIs
- **Quick reference**: `docs/ncos-api/README.md` - common tasks and examples
- **Status API** (read-only): WAN, GPS, modem, system - see `docs/ncos-api/status/`
- **Config API** (settings): 500+ paths - see `docs/ncos-api/config/PATHS.md`
- **Control API** (actions): reboot, ping, GPIO - see `docs/ncos-api/control/`
- **DTD API** (structure): `/api/dtd/config/path` shows exact field types and requirements
- **When searching for an API path**: use `grep -r "keyword" docs/ncos-api/status/ --include="*.md"` to find the right doc file
- Use `cp.get('status/path')` for reads, `cp.put('control/path', value)` for actions
- **Control API via REST**: Use form data format: `curl -u admin:pass -X PUT http://router/api/control/path -d "data=value"` (NOT JSON)
- **Control API via SDK**: Use `cp.put('control/path', value)` - SDK handles encoding automatically
- **Reboot examples**: REST: `curl -u admin:pass -X PUT http://router/api/control/system/reboot -d "data=1"` | SDK: `cp.put('control/system/reboot', 1)`

## CRITICAL: API Verification Workflow (MANDATORY)

**BEFORE writing ANY code that uses an API path:**

1. **STOP** - Do NOT assume fields exist
2. **CHECK DTD**: `curl -s -u admin:pass http://router/api/dtd/config/path | python3 -m json.tool`
3. **SEARCH docs**: `grep -r "api/path" docs/ncos-api/ --include="*.md"`
4. **TEST with curl**: `curl -s -u admin:pass http://router/api/status/path | python3 -m json.tool`
5. **VERIFY fields** - Only use fields that actually exist in the response
6. **THEN code** - Write code based on verified structure

**CRITICAL: ALWAYS use REST API with basic auth (curl -u admin:pass), NEVER use SSH for API validation**

**If you skip these steps, you WILL create broken code.**

**NEVER EVER:**
- Assume a field exists without testing
- Make up API structures based on what "should" be there
- Prioritize speed over correctness
- Write code first and test later
- Use SSH for API validation - always use REST with basic auth

## When to Use Helpers vs Direct API Calls

**Use cp.py helpers for:**
- Simple checks (is WAN connected?)
- Getting basic values (uptime, client count)
- Quick status queries

**Use direct API calls for:**
- Detailed data structures (full WAN device info)
- Dashboard/UI data (need all fields)
- Complex nested objects

## Common API Structures (Quick Reference)

```python
# System - dict with cpu (fractions!), memory (bytes), uptime (seconds), temperature (C)
data = cp.get('status/system')
cpu_percent = (data.get('cpu', {}).get('user', 0) + data.get('cpu', {}).get('system', 0)) * 100

# Disk - dict with disk_usage nested object
data = cp.get('status/mount')
disk = data.get('disk_usage', {})  # {'total_bytes': int, 'free_bytes': int}

# WAN - dict keyed by device name
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

# LAN clients - list of dicts
clients = cp.get('status/lan/clients')  # [{'ip_address': str, 'mac': str, 'hostname': str}, ...]

# Client usage - detailed bandwidth tracking (requires client usage monitoring enabled)
usage = cp.get('status/client_usage')  # {'enabled': bool, 'stats': [{'mac': str, 'ip': str, 'up_bytes': int, 'down_bytes': int, ...}]}

# Firewall conntrack - list of connection tracking entries
fw = cp.get('status/firewall')  # {'conntrack': [...], 'state_entry_count': int}
conntrack = fw.get('conntrack', [])  # [{'id': int, 'orig_src': str, 'orig_dst': str, 'orig_bytes': int, 'reply_bytes': int, 'tcp_state': str, ...}]
# CRITICAL: Track by connection 'id' field to avoid double-counting stale entries
# CRITICAL: Connections persist in conntrack after traffic stops - check byte increments for activity
# CRITICAL: Initialize global tracker with zero bytes, calculate deltas each cycle - only deltas count as activity
# CRITICAL: Filter out closing TCP states (TIME_WAIT, CLOSE_WAIT, FIN_WAIT*, LAST_ACK, CLOSING)
# CRITICAL: Track by MAC address not IP when correlating with clients - IPs can change (DHCP renewal)
# CRITICAL: Resolve all IPs for a domain - CDNs/load balancers use multiple IPs (use socket.getaddrinfo with AF_INET for IPv4 only)
# PATTERN: Global conn tracker: {conn_id: {'tx': bytes, 'rx': bytes, 'last_seen': time}}
# PATTERN: Per-cycle deltas: delta = current_bytes - tracker[conn_id]['bytes'], then update tracker
# PATTERN: Activity detection: only count as active when delta > 0, not just when connection exists

# DHCP leases - hostname, network, SSID info for clients
dhcpd = cp.get('status/dhcpd')  # {'leases': [{'ip_address': str, 'mac': str, 'hostname': str, 'network': str, 'ssid': str, ...}]}

# ARP table - raw text output from system ARP cache
arpdump = cp.get('status/routing/cli/arpdump')  # String with lines: "Type Interface State Link_Address IP_Address"
# CRITICAL: Parse line by line, split by whitespace
# CRITICAL: Only REACHABLE entries are active connections
# CRITICAL: Check for IPv4 by testing if ':' NOT in IP (IPv6 has colons)
# CRITICAL: Interface names have trailing digits (primarylan3) - strip with re.sub(r'\d+$', '', interface)
# PATTERN: parts = line.split(); if parts[0]=='ethernet' and parts[2]=='REACHABLE' and ':'not in parts[4]

# LAN networks - get network info by interface name
info = cp.get('status/lan/networks/{interface}/info')  # {'name': str, 'vlan_id': int, ...}
# CRITICAL: Interface name must NOT have trailing digit (use 'primarylan' not 'primarylan3')
# CRITICAL: Network 'name' field is used to match firewall filter policies

# LAN config - array of LAN configurations
lans = cp.get('config/lan')  # [{'_id_': str, 'name': str, 'ip_address': str, 'netmask': str, 'enabled': bool, ...}]
# CRITICAL: Returns array of dicts, NOT dict keyed by path
# CRITICAL: Each LAN has 'name' field that matches filter policy names

# Firewall filter policies - ZFW MAC/IP filtering
policies = cp.get('config/security/zfw/filter_policies')  # [{'_id_': str, 'name': str, 'default_action': str, 'rules': [...]}]
# CRITICAL: Match policy by 'name' field to network name from status/lan/networks
# CRITICAL: Must get/put entire rules array - cannot update individual rules
# CRITICAL: MAC filtering uses src.mac array: [{'identity': 'aa:bb:cc:dd:ee:ff'}]
# PATTERN: Get rules, modify array, put back: cp.put(f'config/security/zfw/filter_policies/{_id_}/rules', rules)
# Rule structure: {'action': 'deny'|'allow', 'name': str, 'priority': int, 'ip_version': 'ip4'|'ip6',
#                  'src': {'ip': [], 'mac': [{'identity': str}], 'port': []},
#                  'dst': {'ip': [], 'port': []}, 'protocols': [], 'app_sets': []}

# QoS - dict with queues and rules arrays
qos = cp.get('config/qos')  # {'enabled': bool, 'queues': [...], 'rules': [...]}
# CRITICAL: Must put entire qos object, cannot update rules/queues separately
# CRITICAL: QoS rules use IP addresses only (lipaddr/lmask), NO MAC address support
# PATTERN: Use prefixes to identify app-managed resources (e.g., 'MyApp-' prefix for queue/rule names)
# PATTERN: For per-client limits with shared queues, create queue per unique limit, not per client
```

**CRITICAL: status/lan/clients does NOT have rx_bytes/tx_bytes - use status/client_usage for bandwidth data**
**CRITICAL: QoS rules do NOT support MAC addresses - only IP addresses via lipaddr/lmask fields**
**CRITICAL: Firewall conntrack entries have unique 'id' field - track by ID to avoid counting stale connections**
**CRITICAL: ARP dump interface names have trailing digits - strip them before looking up network info**
**CRITICAL: Firewall filter policies require full rules array put - cannot update individual rules**

**See @docs/ncos-api/README.md for full examples and all API paths**
