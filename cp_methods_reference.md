# CP Module Methods Reference

This document lists all available methods when importing the `cp` module for NCOS SDK applications.

## Core Communication Methods

### Basic CRUD Operations
- `get(base: str, query: str = '', tree: int = 0)` → `Optional[Dict[str, Any]]`
- `post(base: str, value: Any = '', query: str = '')` → `Optional[Dict[str, Any]]`
- `put(base: str, value: Any = '', query: str = '', tree: int = 0)` → `Optional[Dict[str, Any]]`
- `delete(base: str, query: str = '')` → `Optional[Dict[str, Any]]`
- `decrypt(base: str, query: str = '', tree: int = 0)` → `Optional[Dict[str, Any]]`
- `patch(value: List[Any])` → `Optional[Dict[str, Any]]`

### Logging and Alerts
- `log(value: str = '')` → `None`
- `alert(value: str = '')` → `Optional[Dict[str, Any]]`

## Event Handling Methods

- `register(action: str = 'set', path: str = '', callback: Callable = None, *args: Any)` → `Dict[str, Any]`
- `on(action: str = 'set', path: str = '', callback: Callable = None, *args: Any)` → `Dict[str, Any]` (alias for register)
- `unregister(eid: int = 0)` → `Dict[str, Any]`

## Device Information Methods

- `get_uptime()` → `int`
- `get_device_mac(format_with_colons: bool = False)` → `Optional[str]`
- `get_device_serial_num()` → `Optional[str]`
- `get_device_product_type()` → `Optional[str]`
- `get_device_name()` → `Optional[str]`
- `get_device_firmware(include_build_info: bool = False)` → `str`

## Network Status Methods

### WAN/LAN Status
- `get_wan_status()` → `Dict[str, Any]`
- `get_wan_devices()` → `Dict[str, Any]`
- `get_wan_modem_diagnostics(device_id: str)` → `Dict[str, Any]`
- `get_wan_modem_stats(device_id: str)` → `Dict[str, Any]`
- `get_wan_ethernet_info(device_id: str)` → `Dict[str, Any]`
- `get_lan_status()` → `Dict[str, Any]`
- `get_lan_clients()` → `Dict[str, Any]`
- `get_lan_networks()` → `Dict[str, Any]`
- `get_lan_devices()` → `Dict[str, Any]`
- `get_lan_statistics()` → `Dict[str, Any]`
- `get_lan_device_stats(device_name: str)` → `Dict[str, Any]`
- `get_wlan_status()` → `Optional[Dict[str, Any]]`
- `get_wlan_clients()` → `List[Dict[str, Any]]`
- `get_wlan_radio_status()` → `List[Dict[str, Any]]`
- `get_wlan_radio_by_band(band: str = '2.4 GHz')` → `Optional[Dict[str, Any]]`
- `get_wlan_channel_info(band: Optional[str] = None, include_survey: bool = False)` → `Dict[str, Any]`
- `get_wlan_client_count()` → `int`
- `get_wlan_client_count_by_band()` → `Dict[str, int]`
- `get_wlan_events()` → `Dict[str, Any]`
- `get_wlan_region_config()` → `Dict[str, Any]`
- `get_wlan_remote_status()` → `Dict[str, Any]`
- `get_wlan_state()` → `str`
- `get_wlan_trace()` → `List[Dict[str, Any]]`
- `get_wlan_debug()` → `Dict[str, Any]`

### Client Information
- `get_ipv4_wired_clients()` → `List[Dict[str, Any]]`
- `get_ipv4_wifi_clients()` → `List[Dict[str, Any]]`
- `get_ipv4_lan_clients()` → `Dict[str, List[Dict[str, Any]]]`
- `get_connected_wans(max_retries: int = 10)` → `List[str]`
- `get_sims(max_retries: int = 10)` → `List[str]`

## GPS and Location Methods

- `get_gps_status()` → `Dict[str, Any]`
- `get_lat_long(max_retries: int = 5, retry_delay: float = 0.1)` → `Tuple[Optional[float], Optional[float]]`
- `dec(deg: float, min: float = 0.0, sec: float = 0.0)` → `float`

## System Status Methods

- `get_system_status()` → `Dict[str, Any]`
- `get_system_resources(cpu: bool = True, memory: bool = True, storage: bool = False)` → `Dict[str, str]`
- `get_temperature(unit: str = 'celsius')` → `Optional[float]`
- `get_power_usage(include_components: bool = True)` → `Optional[Dict[str, Any]]`
- `get_ncm_status(include_details: bool = False)` → `Optional[str]`
- `get_wan_devices_status()` → `Optional[Dict[str, Any]]`
- `get_modem_status()` → `Optional[Dict[str, Any]]`
- `get_signal_strength()` → `Optional[Dict[str, Any]]`

## Configuration Management Methods

### Appdata Management
- `get_appdata(name: str = '')` → `Optional[str]`
- `post_appdata(name: str = '', value: str = '')` → `None`
- `put_appdata(name: str = '', value: str = '')` → `None`
- `delete_appdata(name: str = '')` → `None`

### Certificate Management
- `get_ncm_api_keys()` → `Dict[str, Optional[str]]`
- `extract_cert_and_key(cert_name_or_uuid: str = '')` → `Tuple[Optional[str], Optional[str]]`
- `get_certificates()` → `List[Dict[str, Any]]`
- `get_certificate_by_name(cert_name: str)` → `Optional[Dict[str, Any]]`
- `get_certificate_by_uuid(cert_uuid: str)` → `Optional[Dict[str, Any]]`
- `get_expiring_certificates(days_threshold: int = 30)` → `List[Dict[str, Any]]`
- `get_certificate_summary()` → `Dict[str, Any]`

## Wait/Utility Methods

- `wait_for_uptime(min_uptime_seconds: int = 60)` → `None`
- `wait_for_ntp(timeout: int = 300, check_interval: int = 1)` → `bool`
- `wait_for_wan_connection(timeout: int = 300)` → `bool`
- `wait_for_modem_connection(timeout: int = 300, check_interval: float = 1.0)` → `bool`
- `wait_for_gps_fix(timeout: int = 300, check_interval: float = 1.0)` → `bool`

## Control Methods

### Device Control
- `reboot_device(force: bool = False)` → `None`
- `factory_reset()` → `bool`

### Network Control
- `reset_modem(modem_id: Optional[str] = None, force: bool = False)` → `bool`
- `reset_wlan(force: bool = False)` → `bool`

### System Control
- `clear_logs()` → `bool`
- `restart_service(service_name: str, force: bool = False)` → `bool`
- `set_log_level(level: str = 'info')` → `bool`

## Specialized Status Methods

- `get_openvpn_status()` → `Dict[str, Any]`
- `get_hotspot_status()` → `Optional[Dict[str, Any]]`
- `get_obd_status()` → `Dict[str, Any]`
- `get_qos_status()` → `Dict[str, Any]`
- `get_firewall_status()` → `Dict[str, Any]`
- `get_dns_status()` → `Dict[str, Any]`
- `get_dhcp_status()` → `Dict[str, Any]`
- `get_dhcp_leases()` → `Optional[List[Dict[str, Any]]]`
- `get_routing_table()` → `Optional[Dict[str, Any]]`
- `get_certificate_status()` → `Optional[Dict[str, Any]]`
- `get_storage_status(include_detailed: bool = False)` → `Optional[Dict[str, Any]]`
- `get_usb_status(include_all_ports: bool = False)` → `Optional[Dict[str, Any]]`
- `get_poe_status()` → `Optional[Dict[str, Any]]`
- `get_sensors_status()` → `Optional[Dict[str, Any]]`
- `get_services_status()` → `Optional[Dict[str, Any]]`
- `get_apps_status()` → `Optional[Dict[str, Any]]`
- `get_event_status()` → `Optional[Dict[str, Any]]`
- `get_flow_statistics()` → `Optional[Dict[str, Any]]`
- `get_client_usage()` → `Optional[Dict[str, Any]]`
- `get_vpn_status()` → `Optional[Dict[str, Any]]`
- `get_security_status()` → `Optional[Dict[str, Any]]`
- `get_iot_status()` → `Optional[Dict[str, Any]]`
- `get_sdwan_status()` → `Optional[Dict[str, Any]]`
- `get_comprehensive_status(include_detailed: bool = True, include_clients: bool = True)` → `Optional[Dict[str, Any]]`

## Specialized Helper Methods

### QoS Methods
- `get_qos_queues()` → `List[Dict[str, Any]]`
- `get_qos_queue_by_name(queue_name: str = '')` → `Optional[Dict[str, Any]]`
- `get_qos_traffic_stats()` → `Dict[str, Any]`

### DHCP Methods
- `get_dhcp_clients_by_interface(interface_name: str = '')` → `List[Dict[str, Any]]`
- `get_dhcp_clients_by_network(network_name: str = '')` → `List[Dict[str, Any]]`
- `get_dhcp_client_by_mac(mac_address: str = '')` → `Optional[Dict[str, Any]]`
- `get_dhcp_client_by_ip(ip_address: str = '')` → `Optional[Dict[str, Any]]`
- `get_dhcp_interface_summary()` → `Dict[str, Any]`

### Routing Methods
- `get_bgp_status()` → `Dict[str, Any]`
- `get_ospf_status()` → `Dict[str, Any]`
- `get_static_routes()` → `List[Dict[str, Any]]`
- `get_routing_policies()` → `List[Dict[str, Any]]`
- `get_routing_table_by_name(table_name: str)` → `List[Dict[str, Any]]`
- `get_arp_table()` → `str`
- `get_route_summary()` → `Dict[str, Any]`

### Firewall Methods
- `get_firewall_connections()` → `List[Dict[str, Any]]`
- `get_firewall_hitcounters()` → `List[Dict[str, Any]]`
- `get_firewall_marks()` → `Dict[str, Any]`
- `get_firewall_state_timeouts()` → `Dict[str, Any]`
- `get_firewall_connections_by_protocol(protocol: int = 6)` → `List[Dict[str, Any]]`
- `get_firewall_connections_by_ip(ip_address: str = '')` → `List[Dict[str, Any]]`
- `get_firewall_summary()` → `Dict[str, Any]`

## WAN Profile Management Methods

### Profile Retrieval
- `get_wan_profiles()` → `Dict[str, Any]`
- `get_wan_device_profile(device_id: str)` → `Optional[Dict[str, Any]]`
- `get_wan_profile_by_trigger_string(trigger_string: str)` → `Optional[Dict[str, Any]]`
- `get_wan_profile_by_name(profile_name: str)` → `Optional[Dict[str, Any]]`
- `get_wan_device_summary()` → `Dict[str, Any]`

### Profile Configuration
- `set_wan_device_priority(device_id: str, new_priority: float)` → `bool`
- `make_wan_device_highest_priority(device_id: str)` → `bool`
- `enable_wan_device(device_id: str)` → `bool`
- `disable_wan_device(device_id: str)` → `bool`
- `set_wan_device_default_connection_state(device_id: str, connection_state: str)` → `bool`
- `set_wan_device_bandwidth(device_id: str, ingress_kbps: int = None, egress_kbps: int = None)` → `bool`
- `reorder_wan_profiles(device_priorities: Dict[str, float])` → `bool`

## Utility Methods

- `get_logger()` → `Any`
- `uptime()` → `float` (monkey patched version)
- `clean_up_reg(signal: Any, frame: Any)` → `None`

---

## Usage Examples

### Basic Usage
```python
import cp

# Get device information
device_name = cp.get_device_name()
uptime = cp.get_uptime()

# Get network status
wan_status = cp.get_wan_status()
lan_clients = cp.get_ipv4_lan_clients()

# Log information
cp.log(f"Device {device_name} has been up for {uptime} seconds")
```

### Event Handling
```python
import cp

def config_change_callback(path, value, args):
    cp.log(f"Configuration changed: {path} = {value}")

# Register for configuration changes
event_id = cp.register('put', '/config/system/logging/level', config_change_callback)
```

### Status Monitoring
```python
import cp

# Get comprehensive status
status = cp.get_comprehensive_status()

# Wait for services to be ready
cp.wait_for_wan_connection()
cp.wait_for_gps_fix()
```

### WAN Profile Management
```python
import cp

# Get all WAN profiles
profiles = cp.get_wan_profiles()

# Set a device to highest priority
cp.make_wan_device_highest_priority("mdm-123456")

# Enable/disable devices
cp.enable_wan_device("ethernet-1")
cp.disable_wan_device("mdm-789012")

# Set connection state and bandwidth
cp.set_wan_device_default_connection_state("mdm-123456", "alwayson")
cp.set_wan_device_bandwidth("mdm-123456", ingress_kbps=5000, egress_kbps=1000)
```

This comprehensive list shows that the `cp` module provides extensive functionality for interacting with NCOS routers, including status monitoring, network operations, system control, and WAN profile management.
