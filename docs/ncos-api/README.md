# NCOS API Documentation

Comprehensive NCOS (NetCloud OS) API documentation for Cradlepoint SDK application development.

## Documentation Structure

### API Trees
- [status/](status/README.md) - Status API (read-only, 87 endpoints) - WAN, GPS, modem, system health
- [config/](config/README.md) - Config API (persistent settings, 500+ paths) - WAN rules, firewall, features
- [control/](control/README.md) - Control API (actions) - Reboot, ping, GPIO, speedtest
- [state/](state/README.md) - State API (internal use)

### Reference Files
- [config/PATHS.md](config/PATHS.md) - Complete config path index
- [FEATURES_TO_ENABLE.md](FEATURES_TO_ENABLE.md) - Feature flags and UUIDs
- [config/dtd/NCOS-DTD-7.25.101.json](config/dtd/NCOS-DTD-7.25.101.json) - Full config schema

### Scripts
- **explore_status.py** - Query live router: `python3 explore_status.py status/wan/connection_state`
- **generate_config_paths.py** - Regenerate config index: `python3 generate_config_paths.py`

## API Access Methods

| Method | Use Case | Authentication |
|--------|----------|----------------|
| **SDK (on router)** | SDK apps | None (local only) |
| **REST (HTTP)** | Remote queries, scripts | Basic auth (`admin:password`) |
| **SSH CLI** | Interactive exploration | SSH login |

```python
# SDK - cp.get() returns data directly (NOT wrapped in {"success": true, "data": ...})
import cp
result = cp.get('status/wan/connection_state')  # returns 'connected' string directly

# REST - HTTP API returns wrapped response
curl -u admin:password "http://ROUTER_IP/api/status/wan/connection_state"
# Returns: {"success": true, "data": "connected"}

# SSH CLI
ssh admin@ROUTER_IP
get status/wan/connection_state
```

**CRITICAL: cp.get() unwraps the response automatically. Never do `cp.get('status/system').get('data')` - the data IS the return value.**

## Common Tasks

### Monitor WAN Connection
```python
import cp

# cp.get('status/wan/connection_state') returns string: 'connected' or 'disconnected'
state = cp.get('status/wan/connection_state')
if state == 'connected':
    # cp.get('status/wan/primary_device') returns string device name like 'mdm-41949674'
    device = cp.get('status/wan/primary_device')
    ipinfo = cp.get('status/wan/ipinfo')
    cp.log(f'Connected via {device}: {ipinfo.get("ip_address")}')

# cp.get('status/wan/devices') returns dict keyed by device name:
# {'ethernet-wan': {...}, 'mdm-41949674': {...}}
devices = cp.get('status/wan/devices') or {}
for name, dev in devices.items():
    # Each device has: info, status, diagnostics dicts
    link_state = dev.get('status', {}).get('link_state')  # 'up', 'down', 'unknown'
    model = dev.get('info', {}).get('model')
    cp.log(f'{name}: {model} - {link_state}')
```

### Get WAN Traffic Stats
```python
import cp

stats = cp.get('status/wan/stats')
if stats:
    in_bytes = stats.get('in', 0)
    out_bytes = stats.get('out', 0)
    cp.log(f'RX: {in_bytes} bytes, TX: {out_bytes} bytes')
```

### Reboot Router
```python
import cp
cp.put('control/system/reboot', 1)
```

### Read/Write GPIO
```python
import cp

# Read
gpio = cp.get('status/gpio')
led_state = gpio.get('LED_SS_0')

# Write
cp.put('control/gpio/LED_SS_0', 1)  # On
cp.put('control/gpio/LED_SS_0', 0)  # Off
```

### Check System Health
```python
import cp

# cp.get() returns dict directly with these fields:
# - uptime: float (seconds)
# - cpu: {'user': float, 'system': float} - fractions (0.05 = 5%), NOT percentages
# - memory: {'memtotal': int, 'memavailable': int} - bytes
# - temperature: int (degrees C)
sys = cp.get('status/system')
temp = sys.get('temperature', 0)
uptime = sys.get('uptime', 0)
load = sys.get('load_avg', {}).get('1min', 0)

# Convert CPU fractions to percentages
cpu = sys.get('cpu', {})
cpu_percent = (cpu.get('user', 0) + cpu.get('system', 0)) * 100

cp.log(f'Temp: {temp}°C, Uptime: {uptime}s, Load: {load}, CPU: {cpu_percent:.1f}%')
```

### Check Disk Usage
```python
import cp

# cp.get('status/mount') returns dict with 'disk_usage' nested object
mount = cp.get('status/mount')
disk = mount.get('disk_usage', {})
total = disk.get('total_bytes', 0)
free = disk.get('free_bytes', 0)
used = total - free
percent = (used / total * 100) if total > 0 else 0
cp.log(f'Disk: {used // 1024 // 1024 // 1024}GB / {total // 1024 // 1024 // 1024}GB ({percent:.1f}%)')
```

### Monitor LAN Clients
```python
import cp

# cp.get('status/lan/clients') returns list of dicts:
# [{'ip_address': str, 'mac': str, 'hostname': str}, ...]
clients = cp.get('status/lan/clients') or []
for client in clients:
    mac = client.get('mac', 'unknown')
    ip = client.get('ip_address', 'unknown')
    hostname = client.get('hostname', '')
    cp.log(f'{mac} = {ip} ({hostname})')
```

### Get DNS Info
```python
import cp

dns = cp.get('status/dns')
if dns:
    cache = dns.get('cache', {})
    servers = cache.get('servers', [])
    for server in servers:
        addr = server.get('addr', 'unknown')
        queries = server.get('queries', 0)
        cp.log(f'DNS: {addr} ({queries} queries)')
```

### WAN Rules and SIM Profiles

**IMPORTANT: `cp.get_sims()` returns a list of modem UID strings** (e.g. `['mdm-abcd1234']`), NOT dicts. Use these UIDs to look up device status.

**IMPORTANT: `config/wan/rules2` is a list of dicts indexed by position.** Use `cp.get_wan_profiles()` (from cp.py) which wraps this correctly. To update a single field use the indexed path: `cp.put(f'config/wan/rules2/{rule_id}/priority', value)`.

**NEVER** do `cp.put('config/wan/rules2', whole_list)` — update individual fields by rule `_id_`.

```python
import cp

# Get all WAN profiles (sorted by priority)
profiles = cp.get_wan_profiles()  # returns list of dicts
for profile in profiles:
    cp.log(f'{profile["trigger_name"]}: priority={profile["priority"]}')

# Update priority for a specific rule
rule_id = profile['_id_']
cp.put(f'config/wan/rules2/{rule_id}/priority', 1)

# Get SIM UIDs (returns list of strings like 'mdm-abcd1234')
sim_uids = cp.get_sims()
for uid in sim_uids:
    info = cp.get(f'status/wan/devices/{uid}/info') or {}
    sim_slot = info.get('sim')   # e.g. 'sim1'
    port = info.get('port')      # e.g. 'int1'
    config_id = info.get('config_id')  # matches _id_ in rules2
    cp.log(f'{uid}: sim={sim_slot}, port={port}, rule={config_id}')

# Clone a WAN profile for a specific SIM (post to create new rule)
existing = cp.get(f'config/wan/rules2/{rule_id}')
existing.pop('_id_')
existing['trigger_string'] = f'type|is|mdm%sim|is|{sim_slot}%port|is|{port}'
existing['trigger_name'] = f'SIM {sim_slot} {port}'
existing['priority'] = existing['priority'] + 0.1
cp.post('config/wan/rules2/', existing)
```

**Common trigger_string patterns:**
```
type|is|ethernet                                    # Ethernet WAN
type|is|mdm                                         # Any cellular
type|is|mdm%sim|is|sim1%port|is|int1               # Internal modem SIM1
type|is|mdm%sim|is|sim2%port|is|int1               # Internal modem SIM2
```

### Run Ookla Speedtest on a Specific SIM

**IMPORTANT: `cp.speedtest()` does NOT exist. `cp.speed_test()` uses netperf (slow, unreliable). Use the Ookla binary approach from AutoInstall_Web.**

Required files (copy from `AutoInstall_Web/`):
- `speedtest_ookla.py` — wraps the `ookla` binary, returns `SpeedtestResults` with `.download`/`.upload` in bps
- `ookla` — the Ookla binary (must be present in app directory)

Pattern: inject a host route to force speedtest server traffic through the target SIM's gateway, run the test, then remove the route.

```python
import socket
import requests
from speedtest_ookla import Speedtest

def resolve_speedtest_ips():
    """Resolve Ookla config server IPs before switching SIM."""
    ips = set()
    try:
        for host in ['www.speedtest.net', 'ookla.com']:
            for info in socket.getaddrinfo(host, 443):
                ips.add(info[4][0])
    except Exception as e:
        cp.log(f'resolve_speedtest_ips error: {e}')
    return list(ips)

def add_speedtest_routes(gateway, ips):
    for ip in ips:
        try:
            cp.post('config/routing/tables/0/routes/', {
                'destination': ip, 'prefix': 32,
                'gateway': gateway, 'metric': 1
            })
        except Exception as e:
            cp.log(f'add route error: {e}')

def remove_speedtest_routes(ips):
    routes = cp.get('config/routing/tables/0/routes/') or []
    for route in routes:
        if route.get('destination') in ips:
            try:
                cp.delete(f'config/routing/tables/0/routes/{route["_id_"]}')
            except Exception as e:
                cp.log(f'remove route error: {e}')

def run_speedtest_on_sim(uid):
    """Run Ookla speedtest bound to a specific SIM's WAN IP."""
    wan_ip = cp.get(f'status/wan/devices/{uid}/status/ipinfo/ip_address')
    gateway = cp.get(f'status/wan/devices/{uid}/status/ipinfo/gateway')
    if not wan_ip or not gateway:
        cp.log(f'No WAN IP/gateway for {uid}')
        return None

    ips = resolve_speedtest_ips()
    add_speedtest_routes(gateway, ips)
    try:
        st = Speedtest(source_address=wan_ip)
        results = st.run()
        return results  # results.download, results.upload in bps
    except Exception as e:
        cp.log(f'Speedtest error: {e}')
        return None
    finally:
        remove_speedtest_routes(ips)
```

**Notes:**
- Resolve IPs *before* switching SIMs (while default route is still up)
- `Speedtest(source_address=wan_ip)` binds the test to the correct interface
- Routes use `prefix: 32` (host routes) and `metric: 1` to take priority
- Always remove routes in a `finally` block

### Monitor Firewall
```python
import cp

fw = cp.get('status/firewall')
if fw:
    state_timeouts = fw.get('state_timeouts', {})
    conn_count = state_timeouts.get('state_entry_count', 0)
    conn_limit = state_timeouts.get('state_entry_limit', 0)
    cp.log(f'Connections: {conn_count}/{conn_limit}')
```

### Check Features
```python
import cp

feat = cp.get('status/feature')
if feat:
    db = feat.get('db', [])
    for entry in db:
        if isinstance(entry, list) and len(entry) >= 2:
            uuid, name = entry[0], entry[1]
            cp.log(f'{name}: {uuid}')
```

### Get Product Info
```python
import cp

prod = cp.get('status/product_info')
if prod:
    model = prod.get('product_name', 'unknown')
    mac = prod.get('mac0', 'unknown')
    mfg = prod.get('manufacturing', {})
    serial = mfg.get('serial_num', 'unknown') if isinstance(mfg, dict) else 'unknown'
    cp.log(f'{model}, MAC: {mac}, SN: {serial}')
```

### Check App Status
```python
import cp

sys = cp.get('status/system')
if sys:
    sdk = sys.get('sdk', {})
    service = sdk.get('service', 'unknown')
    apps = sdk.get('apps', [])
    cp.log(f'SDK service: {service}, Apps: {len(apps)}')
    for app in apps:
        name = app.get('app', {}).get('name', 'unknown')
        state = app.get('state', 'unknown')
        cp.log(f'  {name}: {state}')
```

### Monitor Network Interfaces
```python
import cp

ethernet = cp.get('status/ethernet')
if ethernet and isinstance(ethernet, list):
    for port in ethernet:
        port_name = port.get('port_name', 'unknown')
        link = port.get('link', 'down')
        cp.log(f'{port_name}: {link}')
```

### Monitor VPN Tunnels
```python
import cp

vpn = cp.get('status/vpn')
if vpn:
    tunnels = vpn.get('tunnels', [])
    for tunnel in tunnels:
        name = tunnel.get('name', 'unknown')
        state = tunnel.get('state', 'unknown')
        cp.log(f'{name}: {state}')
```

### Monitor Cellular/Modem
```python
import cp

modem = cp.get('status/modem')
if modem:
    # Structure varies by model - see status/modem.md
    cp.log(f'Modem data present')
```

### Get Modem Signal Diagnostics

**IMPORTANT: `status/wan/devices` returns a dict keyed by UID. Each device has a `status` sub-dict (NOT a string). Connection state is at `device['status']['connection_state']`, not `device['status']`.**

**Signal fields are in `device['diagnostics']` with UPPERCASE keys. Only present on connected modems.**

| Field | Key | Notes |
|-------|-----|-------|
| RSSI (dBm) | `DBM` | NOT `RSSI` |
| RSRP | `RSRP` | LTE/5G only |
| RSRQ | `RSRQ` | LTE/5G only |
| SINR | `SINR` | LTE/5G only |
| Carrier name | `CARRID` | NOT `info.carrier` |
| ICCID | `ICCID` | |
| Radio tech | `RAD_IF` | e.g. `'LTE'`, `'5G'` |

```python
import cp

devices = cp.get('status/wan/devices') or {}
for uid, device in devices.items():
    if not uid.startswith('mdm-'):
        continue
    status = device.get('status', {})
    if not isinstance(status, dict):
        continue
    if status.get('connection_state') != 'connected':
        continue
    diag = device.get('diagnostics', {})
    cp.log(f"{uid}: {diag.get('CARRID')} RSSI={diag.get('DBM')} RSRP={diag.get('RSRP')} SINR={diag.get('SINR')}")
```
