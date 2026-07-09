# cp.py Methods Reference

> Source of truth: `apps/templates/app_template/cp.py`

The `cp` module provides a clean, module-level interface for communicating with NCOS routers. Import and use directly without instantiation:

```python
import cp

cp.log('Hello')
data = cp.get('status/system/uptime')
cp.alert('Something happened')
cp.register('put', 'control/my/path', my_callback)
```

---

## Table of Contents

- [Logging and Alerts](#logging-and-alerts)
- [CRUD Operations](#crud-operations)
- [Event Registration](#event-registration)
- [Appdata Management](#appdata-management)
- [Device Info](#device-info)
- [Wait Helpers](#wait-helpers)
- [GPS and Coordinates](#gps-and-coordinates)
- [WAN and Connectivity](#wan-and-connectivity)
- [LAN and Clients](#lan-and-clients)
- [WLAN (Wireless)](#wlan-wireless)
- [System Status](#system-status)
- [NCM (NetCloud Manager)](#ncm-netcloud-manager)
- [Certificates](#certificates)
- [GPIO](#gpio)
- [Diagnostics](#diagnostics)
- [WAN Profile Management](#wan-profile-management)
- [Device Management](#device-management)
- [Speed Test](#speed-test)
- [User Management](#user-management)
- [Log Monitoring and SMS](#log-monitoring-and-sms)
- [Packet Capture](#packet-capture)
- [File Server](#file-server)
- [DNS](#dns)
- [Comprehensive Status](#comprehensive-status)

---

## Logging and Alerts

### `cp.log(value='')`

Log a message to syslog (router), stdout (container), or console (local).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `str` | `''` | Message to log |

**Returns:** `None`

```python
cp.log('Application started')
cp.log(f'WAN state: {state}')
```

---

### `cp.alert(value='')`

Send a custom alert to NCM. Only works on the router.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `str` | `''` | Alert message text |

**Returns:** `Optional[Dict]` with keys `status` and `data` on router; `None` when running locally.

```python
cp.alert('Link failover detected')
```

---

## CRUD Operations

### `cp.get(base, query='', tree=0)`

GET data from the router config/status tree.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `str` | required | Path to resource (e.g. `'status/system/uptime'`) |
| `query` | `str` | `''` | Optional query string |
| `tree` | `int` | `0` | Tree identifier |

**Returns:** The data at the specified path directly (not wrapped), or `None` on failure.

```python
uptime = cp.get('status/system/uptime')
wan_state = cp.get('status/wan/connection_state')
lan_ip = cp.get('config/lan/0/ip_address')
```

> **Important:** `cp.get()` returns data directly, NOT wrapped in `{"success": true, "data": ...}`.

---

### `cp.put(base, value='', query='', tree=0)`

PUT (update) data in the router config/status tree.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `str` | required | Path to resource |
| `value` | `Any` | `''` | Value to set (will be JSON-serialized) |
| `query` | `str` | `''` | Optional query string |
| `tree` | `int` | `0` | Tree identifier |

**Returns:** `Optional[Dict]` with keys `status` (`'ok'`/`'error'`) and `data`. `None` on connection failure.

```python
cp.put('config/system/system_id', 'MyRouter')
cp.put('control/system/reboot', 'reboot hypmgr')
cp.put('config/wan/rules2/{rule_id}/disabled', True)
```

---

### `cp.post(base, value='', query='')`

POST (create) data in the router config/status tree.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `str` | required | Path to resource |
| `value` | `Any` | `''` | Value to post (will be JSON-serialized) |
| `query` | `str` | `''` | Optional query string |

**Returns:** `Optional[Dict]` with keys `status` and `data` (often the created resource ID). `None` on failure.

```python
cp.post('config/system/sdk/appdata', {"name": "server_url", "value": "https://example.com"})
cp.post('config/system/users/', {"group": "admin", "password": "pass", "username": "sdk_user"})
```

---

### `cp.patch(value)`

PATCH the router config tree (bulk add/remove).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `List` | required | List containing `[adds_dict, removals_list]` |

**Returns:** `Optional[Dict]` with keys `status` and `data`. `None` on failure.

```python
adds = {"system": {"system_id": "NewName"}}
removals = []
cp.patch([adds, removals])
```

---

### `cp.delete(base, query='')`

DELETE data from the router config tree.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `str` | required | Path to resource |
| `query` | `str` | `''` | Optional query string |

**Returns:** `Optional[Dict]` with keys `status` and `data`. `None` on failure.

```python
cp.delete('config/system/sdk/appdata/{item_id}')
```

---

### `cp.decrypt(base, query='', tree=0)`

Decrypt and retrieve encrypted data from the router. **Only works on the router.**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `str` | required | Path to encrypted resource |
| `query` | `str` | `''` | Optional query string |
| `tree` | `int` | `0` | Tree identifier |

**Returns:** Decrypted data, or `None` if running locally or on failure.

```python
key = cp.decrypt('config/certmgmt/certs/{cert_id}/key')
```

---

## Event Registration

### `cp.register(action='put', path='', callback=None, *args)`

Register a callback for a config store event. **Only works on NCOS.**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | `str` | `'put'` | Event action (`'put'`, `'get'`). Use `'put'` for control tree |
| `path` | `str` | `''` | Config store path to monitor |
| `callback` | `Callable` | `None` | Function to invoke when the event fires |
| `*args` | `Any` | | Additional arguments passed to callback as a tuple |

**Callback signature:** `callback(path, value, args)`

**Returns:** `Optional[Dict]` with keys `status` and `data`. `None` on failure.

```python
def on_trigger(path, value, args):
    cp.log(f'{path} changed to {value}')

cp.register('put', 'control/myapp/trigger', on_trigger)
```

> **Important:** The `action` parameter MUST be lowercase `'put'` for control tree paths. Using `'set'` or `'PUT'` silently fails.

**Alias:** `cp.on` is equivalent to `cp.register`.

---

### `cp.unregister(eid=0)`

Unregister a previously registered callback.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `eid` | `int` | `0` | Event ID (stored internally in registry) |

**Returns:** `Optional[Dict]` with keys `status` and `data`. `None` if not found.

---

## Appdata Management

Appdata is stored in `config/system/sdk/appdata` and provides key-value storage for SDK applications.

### `cp.get_appdata(name='')`

Get appdata value by name, or all appdata entries if no name given.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `''` | Appdata field name (case-insensitive match) |

**Returns:**
- If `name` provided: `Optional[str]` value of the matching entry, or `None`.
- If `name` empty: `List[Dict]` of entries, each with `name`, `value`, `_id_`.

```python
url = cp.get_appdata('server_url')
all_fields = cp.get_appdata()  # returns list of dicts
```

> **Important:** Always pass a field name. Calling without args returns a LIST of dicts, not a dict.

---

### `cp.put_appdata(name, value)`

Set appdata value by name. Creates the entry if it doesn't exist, updates if it does.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Appdata field name |
| `value` | `str` | required | Value to set |

**Returns:** `None`

```python
cp.put_appdata('last_sync', '2026-01-15T10:30:00')
```

> **Important:** Takes TWO separate arguments (name, value), NOT a dict. Never write default values to appdata as it overrides NCM group configs.

---

### `cp.post_appdata(name, value)`

Create a new appdata entry (does not check for duplicates).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Appdata field name |
| `value` | `str` | required | Value to set |

**Returns:** `None`

---

### `cp.delete_appdata(name)`

Delete an appdata entry by name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Appdata field name to delete |

**Returns:** `None`

---

## Device Info

### `cp.get_name()`

Get the device name (system_id).

**Returns:** `Optional[str]`

---

### `cp.get_mac(format_with_colons=False)`

Get the device MAC address.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format_with_colons` | `bool` | `False` | If True, return with colons (e.g. `'00:30:44:1A:2B:3C'`) |

**Returns:** `Optional[str]` — MAC address string, or `None`.

---

### `cp.get_serial_number()`

Get the device serial number.

**Returns:** `Optional[str]`

---

### `cp.get_product_type()`

Get the device product name (e.g. `'IBR900-600M'`).

**Returns:** `Optional[str]`

---

### `cp.get_router_model()`

Get the router model (part before first dash in product name, e.g. `'IBR900'`).

**Returns:** `Optional[str]`

---

### `cp.get_firmware_version(include_build_info=False)`

Get the firmware version string.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_build_info` | `bool` | `False` | Include build metadata |

**Returns:** `str` — e.g. `'7.25.4-release'`, or `'Unknown'` on error.

---

### `cp.get_uptime()`

Get router uptime in seconds.

**Returns:** `int` — Uptime in seconds, or `0` on error.

---

### `cp.get_description()`

Get device description.

**Returns:** `Optional[str]`

---

### `cp.get_asset_id()`

Get device asset ID.

**Returns:** `Optional[str]`

---

## Wait Helpers

### `cp.wait_for_uptime(min_uptime_seconds=60, timeout=None)`

Block until router uptime exceeds the specified minimum.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_uptime_seconds` | `int` | `60` | Minimum uptime to wait for |
| `timeout` | `Optional[int]` | `None` | Max seconds to wait, or None for indefinite |

**Returns:** `bool` — `True` if uptime reached, `False` if timeout expired.

---

### `cp.wait_for_ntp(timeout=None, check_interval=1)`

Wait until NTP synchronization is achieved.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `Optional[int]` | `None` | Max seconds to wait |
| `check_interval` | `int` | `1` | Seconds between checks |

**Returns:** `bool` — `True` if NTP synced, `False` if timeout expired.

---

### `cp.wait_for_wan_connection(timeout=None)`

Wait for WAN to reach `'connected'` state.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `Optional[int]` | `None` | Max seconds to wait |

**Returns:** `bool` — `True` if connected, `False` if timeout expired.

---

## GPS and Coordinates

### `cp.dec(deg, minutes=0.0, sec=0.0)`

Convert degrees/minutes/seconds to decimal degrees.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deg` | `float` | required | Degrees component |
| `minutes` | `float` | `0.0` | Minutes component |
| `sec` | `float` | `0.0` | Seconds component |

**Returns:** `Optional[float]` — Decimal degrees rounded to 6 places.

---

### `cp.get_lat_long(max_retries=5, retry_delay=0.1)`

Get GPS latitude and longitude as decimal floats.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | `int` | `5` | Number of retries if GPS fix not available |
| `retry_delay` | `float` | `0.1` | Seconds between retries |

**Returns:** `Tuple[Optional[float], Optional[float]]` — `(latitude, longitude)` or `(None, None)`.

```python
lat, lon = cp.get_lat_long()
if lat is not None:
    cp.log(f'Position: {lat}, {lon}')
```

---

### `cp.get_gps_status()`

Get comprehensive GPS status.

**Returns:** `Dict` with keys:
- `gps_lock` (bool)
- `satellites` (int)
- `latitude` (Optional[float])
- `longitude` (Optional[float])
- `altitude` (Optional[float]) — meters
- `speed` (Optional[float]) — knots
- `heading` (Optional[float])
- `accuracy` (Optional[float])
- `last_fix_age` (Optional[float])

---

## WAN and Connectivity

### `cp.get_wan_connection_state()`

Get the WAN connection state string.

**Returns:** `Optional[str]` — e.g. `'connected'`, `'disconnected'`, `'standby'`.

---

### `cp.get_wan_ip_address()`

Get the WAN IP address.

**Returns:** `Optional[str]`

---

### `cp.get_wan_primary_device()`

Get the primary WAN device UID.

**Returns:** `Optional[str]` — e.g. `'mdm-12345678'`.

---

### `cp.get_connected_wans(max_retries=10)`

Get list of connected WAN device UIDs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | `int` | `10` | Number of retries to get device list |

**Returns:** `List[str]` — Connected WAN device UIDs.

---

### `cp.get_sims(max_retries=10)`

Get list of modem UIDs that have SIMs installed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | `int` | `10` | Number of retries to get device list |

**Returns:** `List[str]` — Modem UIDs with SIMs (excludes NOSIM devices).

---

### `cp.get_wan_status()`

Get comprehensive WAN status with all devices and diagnostics.

**Returns:** `Optional[Dict]` with keys:
- `primary_device` (Optional[str])
- `connection_state` (Optional[str])
- `devices` (List[Dict]) — each with `uid`, `connection_state`, `signal_strength`, `ip_address`, `uptime`

---

### `cp.get_signal_strength(uid=None, include_backlog=False)`

Get signal strength and diagnostics for a cellular modem.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `uid` | `Optional[str]` | `None` | Modem device UID. If None, uses first modem |
| `include_backlog` | `bool` | `False` | Include historical signal data |

**Returns:** `Optional[Dict]` with available signal metrics:
- `signal_strength` (int) — dBm
- `cellular_health_score` (int) — 0-100
- `cellular_health_category` (str) — e.g. `'Good'`, `'Poor'`
- `connection_state` (str)
- `rsrp`, `rsrp_5g`, `rsrq`, `rsrq_5g`, `sinr`, `sinr_5g` (str)
- `dbm`, `rf_band`, `service_type` (str)
- `signal_backlog` (list) — if requested

Only non-empty values are included.

---

### `cp.get_wan_devices()`

Get WAN device list with basic status.

**Returns:** `Optional[Dict]` with keys:
- `primary_device` (Optional[str])
- `devices` (List[Dict]) — each with `uid`, `connection_state`, `signal_strength`, `ip_address`, `uptime`

---

### `cp.get_wan_modem_diagnostics(device_id)`

Get modem diagnostics for a specific WAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID (must start with `'mdm'`) |

**Returns:** `Optional[Dict]` — Raw diagnostics with keys like `RSRP`, `SINR`, `RFBAND`, `CELL_ID`, etc.

---

### `cp.get_wan_modem_stats(device_id)`

Get modem statistics for a specific WAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID (must start with `'mdm'`) |

**Returns:** `Optional[Dict]` — Raw modem stats.

---

### `cp.get_wan_ethernet_info(device_id)`

Get ethernet device info for a specific WAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID (must start with `'ethernet'`) |

**Returns:** `Optional[Dict]` — Raw ethernet info.

---

### `cp.get_wan_devices_status()`

Get raw WAN devices status tree.

**Returns:** `Optional[Dict]` — Maps device UIDs to their full status trees.

---

## LAN and Clients

### `cp.get_lan_clients()`

Get LAN client information split by IPv4/IPv6.

**Returns:** `Dict` with keys:
- `total_ipv4_clients` (int)
- `total_ipv6_clients` (int)
- `ipv4_clients` (List[Dict])
- `ipv6_clients` (List[Dict])

---

### `cp.get_ipv4_wired_clients()`

Get IPv4 wired (non-WiFi) LAN clients with hostname resolution.

**Returns:** `List[Dict]` — each with `mac`, `hostname`, `ip_address`, `network`.

---

### `cp.get_ipv4_wifi_clients()`

Get IPv4 WiFi clients with SSID, signal, and band info.

**Returns:** `List[Dict]` — each with:
- `mac`, `hostname`, `ip_address`
- `radio` (int), `bss` (int), `ssid` (str)
- `network`, `band` (`'2.4'`/`'5'`), `mode` (e.g. `'802.11ac'`)
- `bw` (e.g. `'80 MHz'`), `txrate`, `rssi`, `time`

---

### `cp.get_ipv4_lan_clients()`

Get all IPv4 LAN clients (both wired and WiFi).

**Returns:** `Dict` with keys:
- `wired_clients` (List[Dict])
- `wifi_clients` (List[Dict])

---

### `cp.get_lan_status()`

Get comprehensive LAN status including clients, networks, devices, stats.

**Returns:** `Optional[Dict]` with keys:
- `total_ipv4_clients`, `total_ipv6_clients` (int)
- `lan_stats` (Dict)
- `ipv4_clients`, `ipv6_clients` (List[Dict])
- `networks` (List[Dict]) — each with `name`, `display_name`, `ip_address`, `netmask`, `type`, `devices`
- `devices` (List[Dict]) — each with `name`, `interface`, `link_state`, `type`

---

### `cp.get_lan_networks()`

Get LAN network information.

**Returns:** `Optional[Dict]` with key `networks` (List[Dict]).

---

### `cp.get_lan_devices()`

Get LAN device information.

**Returns:** `Optional[Dict]` with key `devices` (List[Dict]).

---

### `cp.get_lan_statistics()`

Get overall LAN statistics.

**Returns:** `Optional[Dict]` with key `lan_stats` (Dict).

---

### `cp.get_lan_device_stats(device_name)`

Get statistics for a specific LAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_name` | `str` | required | LAN device name |

**Returns:** `Optional[Dict]` — Raw device statistics.

---

## WLAN (Wireless)

### `cp.get_wlan_status()`

Get comprehensive WLAN status.

**Returns:** `Optional[Dict]` — Raw WLAN status tree including state, clients, radio info, events.

---

### `cp.get_wlan_clients()`

Get connected wireless clients.

**Returns:** `List[Dict]` — each with `mac`, `radio`, `bss`, `rssi0`, `txrate`, `mode`, `bw`, `time`.

---

### `cp.get_wlan_radio_status()`

Get wireless radio status for all bands.

**Returns:** `List[Dict]` — each with `band`, `channel`, `channel_list`, `txpower`, `clients`.

---

### `cp.get_wlan_radio_by_band(band='2.4 GHz')`

Get radio status for a specific band.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `band` | `str` | `'2.4 GHz'` | `'2.4 GHz'` or `'5 GHz'` |

**Returns:** `Optional[Dict]` — Radio dict with channel, txpower, clients, etc.

---

### `cp.get_wlan_state()`

Get WLAN operational state.

**Returns:** `str` — e.g. `'On'`, `'Off'`, or `'Unknown'`.

---

### `cp.get_wlan_events()`

Get WLAN events (associate, deauth, disassociate, etc.).

**Returns:** `Dict` — Event types mapped to event data.

---

### `cp.get_wlan_channel_info(band=None, include_survey=False)`

Get channel info for specified band or all bands.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `band` | `Optional[str]` | `None` | Specific band, or None for all |
| `include_survey` | `bool` | `False` | Include channel survey data |

**Returns:** `Dict` with keys:
- `current_channel` (Optional[int])
- `available_channels` (List[int])
- `channel_locked` (bool)
- `txpower` (int)
- `survey_data` (List) — if requested

If no band specified, returns a dict keyed by band name.

---

### `cp.get_wlan_client_count()`

Get count of connected wireless clients.

**Returns:** `int`

---

### `cp.get_wlan_client_count_by_band()`

Get wireless client count per frequency band.

**Returns:** `Dict[str, int]` — e.g. `{'2.4 GHz': 3, '5 GHz': 7}`.

---

## System Status

### `cp.get_system_status()`

Get system status including uptime, CPU, memory, disk, services.

**Returns:** `Optional[Dict]` with keys:
- `uptime` (Optional[int]) — seconds
- `temperature` (Optional[float]) — Celsius
- `cpu_usage` (int) — percentage
- `memory` (Dict) — `total_bytes`, `used_bytes`, `free_bytes`, `percentage_used`
- `disk` (Dict) — `total_bytes`, `used_bytes`, `free_bytes`, `percentage_used`
- `services_running` (int)
- `services_disabled` (int)

---

### `cp.get_temperature(unit='fahrenheit')`

Get device temperature.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `unit` | `str` | `'fahrenheit'` | `'celsius'` or `'fahrenheit'` |

**Returns:** `Optional[float]`

---

### `cp.get_services_status()`

Get system services status.

**Returns:** `Optional[Dict]` — Maps service names to their state dicts.

---

### `cp.get_apps_status()`

Get internal and external (SDK) app status.

**Returns:** `Optional[Dict]` with keys:
- `internal_apps` (List)
- `external_apps` (List)
- `total_apps` (int)
- `running_apps` (int)

---

### `cp.get_dhcp_status()`

Get DHCP status with lease information.

**Returns:** `Optional[Dict]` with keys:
- `total_leases` (int)
- `active_leases` (int)
- `leases` (List[Dict])

---

### `cp.get_dhcp_leases()`

Get DHCP lease list.

**Returns:** `Optional[List[Dict]]` — Lease entries with `mac`, `ip_address`, `hostname`, `expire`, `network`.

---

### `cp.get_dns_status()`

Get DNS status.

**Returns:** `Optional[Dict]` with keys:
- `cache_entries` (int)
- `cache_size` (int)
- `servers_configured` (int)
- `queries_forwarded` (int)

---

### `cp.get_firewall_status()`

Get firewall status.

**Returns:** `Optional[Dict]` with keys:
- `connections_tracked` (int)
- `state_timeouts` (Dict)
- `hitcounters` (List)

---

### `cp.get_openvpn_status()`

Get OpenVPN status.

**Returns:** `Optional[Dict]` with keys:
- `tunnels_configured` (int)
- `tunnels_active` (int)
- `stats_available` (bool)

---

### `cp.get_vpn_status()`

Get combined VPN status (OpenVPN, L2TP, GRE, VXLAN).

**Returns:** `Optional[Dict]` with keys `openvpn`, `l2tp`, `gre`, `vxlan`.

---

### `cp.get_hotspot_status()`

Get hotspot status.

**Returns:** `Optional[Dict]` with keys:
- `clients_connected` (int)
- `sessions_active` (int)
- `domains_allowed` (int)
- `hosts_allowed` (int)
- `rate_limit_triggered` (bool)

---

### `cp.get_qos_status()`

Get QoS status.

**Returns:** `Optional[Dict]` with keys:
- `qos_enabled` (bool)
- `queues_configured` (int)
- `queues_active` (int)
- `total_packets` (int)

---

### `cp.get_obd_status()`

Get OBD (vehicle diagnostics) status.

**Returns:** `Optional[Dict]` with keys:
- `adapter_configured`, `adapter_connected`, `vehicle_connected` (bool)
- `pids_supported`, `pids_enabled` (int)
- `ignition_status` (Optional[str])
- `pids` (List[Dict])

---

### `cp.get_sdwan_status()`

Get SD-WAN advanced status.

**Returns:** `Optional[Dict]` with keys:
- `forward_error_correction` (Dict)
- `link_monitoring` (Dict)
- `quality_of_experience` (Dict)
- `user_mode_driver` (Dict)
- `wan_bonding` (Dict)

---

### `cp.get_routing_table()`

Get routing table information.

**Returns:** `Optional[Dict]` — Raw routing status tree.

---

### `cp.get_flow_statistics()`

Get flow statistics with destination info.

**Returns:** `Optional[Dict]` with keys:
- `total_destinations` (int)
- `total_packets` (int)
- `destinations` (List)

---

### `cp.get_client_usage()`

Get client usage statistics with bandwidth info.

**Returns:** `Optional[Dict]` with keys:
- `enabled` (bool)
- `total_clients` (int)
- `total_traffic` (Dict) — `down_bytes`, `up_bytes`, `total_bytes`
- `stats` (List[Dict])

---

### `cp.get_power_usage(include_components=True)`

Get power usage information.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_components` | `bool` | `True` | Include per-component breakdown |

**Returns:** `Optional[Dict]` with component keys (`system_power`, `cpu_power`, `modem_power`, etc.) and `total`.

---

### `cp.get_storage_status()`

Get storage health status.

**Returns:** `Optional[Dict]` with keys `health` and `slc_health`.

---

### `cp.get_sensors_status()`

Get sensor status.

**Returns:** `Optional[Dict]` with keys `level` and `day`.

---

### `cp.get_iot_status()`

Get IoT status.

**Returns:** `Optional[Dict]` — Raw IoT status tree.

---

### `cp.get_event_status()`

Get system events status.

**Returns:** `Optional[Dict]` — Raw event status tree.

---

### `cp.get_certificate_status()`

Get certificate management status.

**Returns:** `Optional[Dict]` — Raw certificate management status tree.

---

## NCM (NetCloud Manager)

### `cp.get_ncm_status()`

Get NCM connection state.

**Returns:** `Optional[str]` — e.g. `'connected'`, `'disconnected'`.

---

### `cp.get_ncm_router_id()`

Get the router's NCM client ID.

**Returns:** `Optional[str]`

---

### `cp.get_ncm_group_name()`

Get the router's NCM group name.

**Returns:** `Optional[str]`

---

### `cp.get_ncm_account_name()`

Get the router's NCM account name.

**Returns:** `Optional[str]`

---

### `cp.get_ncm_api_keys()`

Get NCM API keys stored in certificate management.

**Returns:** `Optional[Dict]` with keys:
- `'X-ECM-API-ID'`
- `'X-ECM-API-KEY'`
- `'X-CP-API-ID'`
- `'X-CP-API-KEY'`
- `'Bearer Token'`

Each value is the decrypted key string or `None`.

---

## Certificates

### `cp.extract_cert_and_key(cert_name_or_uuid)`

Extract certificate and private key to local `.pem` files. Follows the CA chain to build a full-chain certificate file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cert_name_or_uuid` | `str` | required | Certificate name or UUID |

**Returns:** `Tuple[Optional[str], Optional[str]]` — `(cert_filename, key_filename)` or `(None, None)`.

```python
cert_file, key_file = cp.extract_cert_and_key('MyCert')
# Creates MyCert.pem and MyCert_key.pem in the working directory
```

---

## GPIO

### `cp.get_gpio(gpio_name=None, router_model=None)`

Get GPIO value(s) for the router.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gpio_name` | `Optional[str]` | `None` | Specific GPIO (e.g. `'power_input'`). None returns all |
| `router_model` | `Optional[str]` | `None` | Override auto-detected model |

**Returns:**
- If `gpio_name` specified: single GPIO value (int or bool).
- If `gpio_name` is None: `Dict` mapping GPIO names to values.
- `None` on error or if model not in GPIO_MAP.

**Supported models and GPIOs:**

| Model | Available GPIOs |
|-------|----------------|
| IBR200 | `power_input`, `power_output` |
| IBR600 | `power_input`, `power_output` |
| IBR900 | `power_input`, `power_output`, `sata_1`-`sata_4`, `sata_ignition_sense` |
| IBR1100 | `power_input`, `power_output`, `expander_1`-`expander_3` |
| R920 | `power_input`, `power_output` |
| R980 | `power_input`, `power_output` |
| R1900 | `power_input`, `power_output`, `expander_1`-`expander_3`, `accessory_1` |

---

### `cp.get_all_gpios()`

Get raw GPIO data from `/status/gpio`.

**Returns:** `Dict` — Raw GPIO status mapping GPIO names to values.

---

### `cp.get_available_gpios(router_model=None)`

Get list of available GPIO names for the current router model.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `router_model` | `Optional[str]` | `None` | Override auto-detected model |

**Returns:** `List[str]` — GPIO name strings.

---

## Diagnostics

### `cp.ping_host(host, count=4, packet_size=56)`

Ping a host using the router's diagnostic tools.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | required | Target hostname or IP address |
| `count` | `int` | `4` | Number of ping packets |
| `packet_size` | `int` | `56` | Packet size in bytes |

**Returns:** `Optional[Dict]` with keys:
- `host` (str), `num` (int), `size` (int)
- `tx` (int), `rx` (int), `loss` (float) — percentage
- `min` (float), `avg` (float), `max` (float) — RTT in ms
- `error` (str) — present instead of stats on failure

```python
result = cp.ping_host('8.8.8.8', count=10)
if 'error' not in result:
    cp.log(f'Avg latency: {result["avg"]}ms, loss: {result["loss"]}%')
```

---

### `cp.stop_ping()`

Stop any running ping process.

**Returns:** `Optional[Dict]` — Config store response.

---

### `cp.traceroute_host(host, max_hops=30)`

Perform traceroute to a host using router diagnostics.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | required | Target hostname or IP |
| `max_hops` | `int` | `30` | Maximum number of hops |

**Returns:** `Optional[Dict]` with keys:
- `host` (str)
- `hops` (List[str]) — parsed hop lines
- `hop_count` (int)
- `raw_output` (str) — full traceroute output
- `error` (str) — present on failure

---

### `cp.execute_cli(commands, timeout=10, clean=True)`

Execute CLI commands on the router and return output.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `commands` | `Union[str, List[str]]` | required | Single command or list of commands |
| `timeout` | `int` | `10` | Max seconds to wait for output |
| `clean` | `bool` | `True` | Remove terminal escape sequences |

**Returns:** `Optional[str]` — Command output string.

```python
output = cp.execute_cli('show wan')
output = cp.execute_cli(['show version', 'show interfaces'])
```

---

### `cp.dns_lookup(hostname, record_type='A')`

Perform DNS lookup.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hostname` | `str` | required | Hostname to look up |
| `record_type` | `str` | `'A'` | DNS record type |

**Returns:** `Optional[Dict]` with keys `hostname`, `record_type`, `result`.

---

### `cp.clear_dns_cache()`

Clear the router's DNS cache.

**Returns:** `Optional[Dict]` — Config store response.

---

## WAN Profile Management

### `cp.get_wan_profiles()`

Get all WAN profile rules sorted by priority.

**Returns:** `Optional[List[Dict]]` — Sorted by priority (lowest first). Each dict has keys like `_id_`, `priority`, `trigger_name`, `disabled`, modem settings.

---

### `cp.get_wan_device_profile(device_id)`

Get WAN profile applied to a specific device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID |

**Returns:** `Optional[Dict]` — WAN profile dict.

---

### `cp.set_wan_device_priority(device_id, new_priority)`

Set priority for a WAN device's profile.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID |
| `new_priority` | `float` | required | New priority value (lower = higher priority) |

**Returns:** `bool` — `True` on success.

---

### `cp.make_wan_device_highest_priority(device_id)`

Make a WAN device the highest priority (sets priority lower than all others).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID |

**Returns:** `bool` — `True` on success.

---

### `cp.enable_wan_device(device_id)`

Enable a WAN device.

**Returns:** `bool` — `True` on success.

---

### `cp.disable_wan_device(device_id)`

Disable a WAN device.

**Returns:** `bool` — `True` on success.

---

### `cp.set_wan_device_default_connection_state(device_id, connection_state)`

Set default connection state for a WAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID |
| `connection_state` | `str` | required | `'alwayson'`, `'auto'`, `'ondemand'`, or `'disabled'` |

**Returns:** `bool` — `True` on success.

---

### `cp.set_wan_device_bandwidth(device_id, ingress_kbps=None, egress_kbps=None)`

Set bandwidth limits for a WAN device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `str` | required | WAN device UID |
| `ingress_kbps` | `Optional[int]` | `None` | Ingress limit in kbps |
| `egress_kbps` | `Optional[int]` | `None` | Egress limit in kbps |

**Returns:** `bool` — `True` if all updates succeeded.

---

### `cp.set_manual_apn(device_or_id, new_apn)`

Set manual APN for a modem device or WAN rule.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_or_id` | `str` | required | Modem device UID (`mdm-xxx`) or WAN rule `_id_` |
| `new_apn` | `str` | required | APN string to set |

**Returns:** `Optional[Dict]` with keys `success`, `rule_id`, `new_apn` (or `error`).

---

### `cp.remove_manual_apn(device_or_id)`

Remove manual APN and revert to auto mode.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_or_id` | `str` | required | Modem device UID or WAN rule `_id_` |

**Returns:** `Optional[Dict]` with keys `success`, `rule_id` (or `error`).

---

### `cp.add_advanced_apn(carrier, apn)`

Add an advanced APN to the custom APNs list.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `carrier` | `str` | required | Carrier name |
| `apn` | `str` | required | APN value |

**Returns:** `Optional[Dict]` with keys `success`, `carrier`, `apn` (or `note: 'already exists'`).

---

### `cp.delete_advanced_apn(carrier_or_apn)`

Delete advanced APN entries matching carrier or APN name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `carrier_or_apn` | `str` | required | Carrier name or APN to match |

**Returns:** `Optional[Dict]` with keys `success`, `deleted_count` (or `error`).

---

### `cp.get_wan_device_summary()`

Get summary of all WAN devices with profile info.

**Returns:** `Optional[Dict]` with keys:
- `devices` (List[Dict]) — each with `uid`, `profile_name`, `priority`, `disabled`, `connection_state` (sorted by priority)
- `profiles` (Optional[List[Dict]])
- `total_devices` (int)

---

## Device Management

### `cp.reboot_device()`

Reboot the router.

**Returns:** `None`

---

### `cp.set_name(name)`

Set device name (system_id).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | New device name |

**Returns:** `Optional[Dict]` with keys `success` and `name`.

---

### `cp.set_description(description)`

Set device description.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `description` | `str` | required | New description |

**Returns:** `Optional[Dict]` with keys `success` and `description`.

---

### `cp.set_asset_id(asset_id)`

Set device asset ID.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `asset_id` | `str` | required | New asset ID |

**Returns:** `Optional[Dict]` with keys `success` and `asset_id`.

---

## Speed Test

### `cp.speed_test(host='', interface='', duration=5, packet_size=0, protocol='tcp', direction='both')`

Perform network speed test using router's netperf.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `''` | Target host (empty for auto-detect) |
| `interface` | `str` | `''` | Network interface (empty for auto-detect via primary WAN) |
| `duration` | `int` | `5` | Test duration in seconds |
| `packet_size` | `int` | `0` | Packet size (0 for default) |
| `protocol` | `str` | `'tcp'` | `'tcp'` or `'udp'` |
| `direction` | `str` | `'both'` | `'recv'`, `'send'`, or `'both'` |

**Returns:** `Optional[Dict]` with keys:
- `download_bps` (float) — bits/sec
- `upload_bps` (float) — bits/sec
- `latency_ms` (float)
- `test_duration` (int)
- `interface` (str)
- `host` (str)
- `protocol` (str)

```python
result = cp.speed_test(interface='rmnet501', duration=10, direction='both')
cp.log(f'Download: {result["download_bps"] / 1e6:.1f} Mbps')
```

---

### `cp.stop_speed_test()`

Stop any running speed test.

**Returns:** `Optional[Dict]` — Config store response.

---

## User Management

### `cp.create_user(username, password, group='admin')`

Create a new user on the router.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | required | Username |
| `password` | `str` | required | Password |
| `group` | `str` | `'admin'` | User group |

**Returns:** `Dict` with keys `success`, `username`, `group`, `result` (or `error`).

---

### `cp.get_users()`

Get list of all users.

**Returns:** `Dict` with keys `success` and `users` (List[Dict] with `username`, `group`, `_id_`).

---

### `cp.delete_user(username)`

Delete a user by username.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | required | Username to delete |

**Returns:** `Dict` with keys `success`, `username`, `result` (or `error`).

---

### `cp.ensure_user_exists(username, password, group='admin')`

Ensure a user exists, creating if needed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | required | Username |
| `password` | `str` | required | Password (used only if creating) |
| `group` | `str` | `'admin'` | User group |

**Returns:** `Dict` with keys `success`, `username`, `action` (`'exists'` or `'created'`).

---

### `cp.ensure_fresh_user(username, group='admin')`

Delete existing user and recreate with a random password.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | required | Username |
| `group` | `str` | `'admin'` | User group |

**Returns:** `Dict` with keys `success`, `username`, `password` (generated), `action` (`'created_fresh'`).

> **Note:** The generated password contains special characters that can break HTTP Basic Auth. For auth use cases, prefer `cp.delete_user()` + `cp.create_user()` with an alphanumeric-only password.

---

### `cp.validate_password(username, password)`

Validate a plaintext password against the stored hash for a user. Supports NCOS `$3$` PBKDF2-HMAC-SHA256 format.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | required | Username to validate |
| `password` | `str` | required | Plaintext password to check |

**Returns:** `Dict` with keys `success`, `valid` (bool), `username` (or `error`).

> **Note:** Only works on-router. The REST API returns masked `$0$` hashes that cannot be validated.

---

## Log Monitoring and SMS

### `cp.monitor_log(pattern=None, callback=None, follow=True, max_lines=0, timeout=0)`

Monitor `/var/log/messages` with optional pattern matching and callback. Runs in a background thread.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | `Optional[str]` | `None` | Regex pattern to filter lines |
| `callback` | `Optional[Callable]` | `None` | Function called with each matching line |
| `follow` | `bool` | `True` | Tail -f behavior |
| `max_lines` | `int` | `0` | Max lines to process (0 = unlimited) |
| `timeout` | `int` | `0` | Timeout in seconds (0 = no timeout) |

**Returns:** `Optional[Dict]` with keys:
- `success` (bool)
- `thread_id` (int)
- `stop_event` (threading.Event) — set to stop monitoring
- `line_queue` (Queue) — lines queued if no callback given

```python
def on_line(line):
    cp.log(f'Matched: {line}')

monitor = cp.monitor_log(pattern='error', callback=on_line, timeout=60)
# Later...
cp.stop_monitor_log(monitor)
```

---

### `cp.stop_monitor_log(monitor_result)`

Stop a running `monitor_log` operation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `monitor_result` | `Dict` | required | Return value from `monitor_log()` |

**Returns:** `Dict` with keys `success` and `stopped` (or `error`).

---

### `cp.monitor_sms(callback, timeout=0)`

Monitor for SMS messages and parse phone/message to callback.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `callback` | `Callable` | required | `callback(phone_number, message, raw_line)` |
| `timeout` | `int` | `0` | Timeout in seconds (0 = no timeout) |

**Returns:** `Optional[Dict]` — Same as `monitor_log()` return value.

---

### `cp.stop_monitor_sms(monitor_result)`

Stop a running SMS monitor.

**Returns:** `Dict` — Same as `stop_monitor_log()`.

---

### `cp.send_sms(phone_number, message, port=None)`

Send an SMS message via CLI.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `phone_number` | `str` | required | Destination phone number |
| `message` | `str` | required | Message text |
| `port` | `Optional[str]` | `None` | Modem port (auto-detected if None) |

**Returns:** `Optional[str]` — CLI output string.

---

## Packet Capture

### `cp.start_packet_capture(interface='any', filter_expr='', count=20, timeout=600, url='', filename='')`

Start packet capture using tcpdump API.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interface` | `str` | `'any'` | Network interface |
| `filter_expr` | `str` | `''` | BPF filter expression |
| `count` | `int` | `20` | Number of packets (0 = unlimited) |
| `timeout` | `int` | `600` | Capture timeout in seconds |
| `url` | `str` | `''` | Upload URL (CloudShark) |
| `filename` | `str` | `''` | Pcap filename (auto-generated if empty) |

**Returns:** `Optional[Dict]` with keys:
- `filename` (str)
- `parameters` (Dict)
- `api_url` (str)
- `capture_result` (Any)

> **Note:** For on-router apps, prefer using the REST tcpdump API directly with HTTP Basic Auth instead of this helper. See the API reference docs for details.

---

### `cp.stop_packet_capture()`

Stop packet capture (informational — captures stop via timeout/count).

**Returns:** `Dict` with `message` and `suggestion`.

---

### `cp.download_packet_capture(filename, local_path=None, capture_params=None)`

Download a captured pcap file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filename` | `str` | required | Pcap filename |
| `local_path` | `Optional[str]` | `None` | Local save path (default: current directory) |
| `capture_params` | `Optional[Dict]` | `None` | Original capture parameters for URL construction |

**Returns:** `Optional[Dict]` with keys `filename`, `local_path`, `file_size`, `success`.

---

## File Server

### `cp.start_file_server(folder_path='files', port=8000, host='0.0.0.0', title='File Download')`

Start a web file server with a responsive UI for downloading files. Runs in a background thread.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder_path` | `str` | `'files'` | Relative path to serve files from |
| `port` | `int` | `8000` | Port number |
| `host` | `str` | `'0.0.0.0'` | Bind address |
| `title` | `str` | `'File Download'` | Page title shown in the UI |

**Returns:** `Optional[Dict]` with keys:
- `status` (str): `'started'`
- `url` (str): e.g. `'http://0.0.0.0:8000'`
- `folder_path` (str): Absolute path being served
- `port` (int)

```python
server = cp.start_file_server(folder_path='logs', port=9000, title='Log Files')
cp.log(f'File server at {server["url"]}')
```

---

## DNS

### `cp.dns_lookup(hostname, record_type='A')`

Perform DNS lookup.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hostname` | `str` | required | Hostname to look up |
| `record_type` | `str` | `'A'` | DNS record type |

**Returns:** `Optional[Dict]` with keys `hostname`, `record_type`, `result`.

---

### `cp.clear_dns_cache()`

Clear the router's DNS cache.

**Returns:** `Optional[Dict]` — Config store response.

---

## Comprehensive Status

### `cp.get_comprehensive_status()`

Get a comprehensive status report of the router in a single call.

**Returns:** `Optional[Dict]` with keys:
- `system` (Optional[Dict]) — from `get_system_status()`
- `wan` (Optional[Dict]) — from `get_wan_status()`
- `lan` (Dict) — from `get_lan_clients()`
- `wlan_state` (str) — from `get_wlan_state()`
- `gps` (Dict) — from `get_gps_status()`
- `ncm` (Optional[str]) — NCM connection state
- `firmware` (str) — firmware version
- `temperature` (Optional[float])

---

### `cp.get_security_status()`

Get combined security status.

**Returns:** `Optional[Dict]` with keys:
- `firewall` (Optional[Dict])
- `security` (Any) — raw security status
- `certificates` (Optional[Dict])

---

## Backward Compatibility

The module provides `cp.CSClient` and `cp.EventingCSClient` as shim classes for code written against the older cp.py. They delegate all methods to the module-level functions:

```python
# Old style (still works):
client = cp.CSClient('app_name')
client.get('status/system/uptime')

# Preferred style:
cp.get('status/system/uptime')
```

---

## Environment Behavior

The `cp` module automatically detects its runtime environment:

| Environment | `cp.get()`/`cp.put()` | `cp.log()` | `cp.register()` |
|-------------|----------------------|------------|-----------------|
| **On router** (NCOS) | Unix socket to config store | syslog | Full event system |
| **Local dev** | HTTPS REST API to device via `sdk_settings.ini` | `print()` | Not available |
| **Container** | HTTPS REST API | stdout | Not available |

For local development, configure `sdk_settings.ini` in the project root:

```ini
[sdk]
dev_client_ip = 192.168.0.1
dev_client_username = admin
dev_client_password = your_password
```
