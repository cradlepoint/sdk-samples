# CP Module Methods Reference

This document lists all available methods when importing the `cp` module for NCOS SDK applications.

## Quick Index (A–Z)

- `add_advanced_apn`
- `alert`
- `clear_dns_cache`
- `clear_logs`
- `clean_up_reg`
- `create_user`
- `dec`
- `delete`
- `delete_advanced_apn`
- `delete_appdata`
- `delete_user`
- `decrypt`
- `disable_wan_device`
- `dns_lookup`
- `download_packet_capture`
- `enable_wan_device`
- `ensure_fresh_user`
- `ensure_user_exists`
- `execute_cli`
- `extract_cert_and_key`
- `factory_reset`
- `get`
- `get_all_gpios`
- `get_appdata`
- `get_apps_status`
- `get_arp_table`
- `get_asset_id`
- `get_available_gpios`
- `get_available_interfaces`
- `get_bgp_status`
- `get_certificate_by_name`
- `get_certificate_by_uuid`
- `get_certificate_status`
- `get_certificate_summary`
- `get_certificates`
- `get_client_usage`
- `get_comprehensive_status`
- `get_description`
- `get_dhcp_client_by_ip`
- `get_dhcp_client_by_mac`
- `get_dhcp_clients_by_interface`
- `get_dhcp_clients_by_network`
- `get_dhcp_interface_summary`
- `get_dhcp_leases`
- `get_dns_status`
- `get_event_status`
- `get_expiring_certificates`
- `get_firewall_connections`
- `get_firewall_connections_by_ip`
- `get_firewall_connections_by_protocol`
- `get_firewall_hitcounters`
- `get_firewall_marks`
- `get_firewall_state_timeouts`
- `get_firewall_status`
- `get_flow_statistics`
- `get_firmware_version`
- `get_gpio`
- `get_gps_status`
- `get_iot_status`
- `get_ipv4_lan_clients`
- `get_ipv4_wifi_clients`
- `get_ipv4_wired_clients`
- `get_lan_clients`
- `get_lan_device_stats`
- `get_lan_devices`
- `get_lan_networks`
- `get_lan_statistics`
- `get_lan_status`
- `get_logger`
- `get_mac`
- `get_ncm_account_name`
- `get_ncm_api_keys`
- `get_ncm_group_name`
- `get_ncm_router_id`
- `get_name`
- `get_obd_status`
- `get_openvpn_status`
- `get_ospf_status`
- `get_poe_status`
- `get_power_usage`
- `get_product_type`
- `get_qos_queue_by_name`
- `get_qos_queues`
- `get_qos_status`
- `get_qos_traffic_stats`
- `get_raw_gpios`
- `get_route_summary`
- `get_router_model`
- `get_routing_policies`
- `get_routing_table`
- `get_routing_table_by_name`
- `get_sdwan_status`
- `get_security_status`
- `get_services_status`
- `get_signal_strength`
- `get_sims`
- `get_sensors_status`
- `get_static_routes`
- `get_storage_status`
- `get_system_status`
- `get_temperature`
- `get_usb_status`
- `get_users`
- `get_vpn_status`
- `get_wan_connection_state`
- `get_wan_devices`
- `get_wan_devices_status`
- `get_wan_device_profile`
- `get_wan_device_summary`
- `get_wan_ethernet_info`
- `get_wan_ip_address`
- `get_wan_modem_diagnostics`
- `get_wan_modem_stats`
- `get_wan_primary_device`
- `get_wan_profile_by_name`
- `get_wan_profile_by_trigger_string`
- `get_wan_profiles`
- `get_wan_status`
- `get_wlan_channel_info`
- `get_wlan_client_count`
- `get_wlan_client_count_by_band`
- `get_wlan_clients`
- `get_wlan_debug`
- `get_wlan_events`
- `get_wlan_radio_by_band`
- `get_wlan_radio_status`
- `get_wlan_region_config`
- `get_wlan_remote_status`
- `get_wlan_state`
- `get_wlan_status`
- `get_wlan_trace`
- `log`
- `make_wan_device_highest_priority`
- `monitor_log`
- `monitor_sms`
- `network_connectivity_test`
- `packet_capture`
- `ping_host`
- `post`
- `post_appdata`
- `put`
- `put_appdata`
- `reboot_device`
- `register`
- `remove_manual_apn`
- `reorder_wan_profiles`
- `reset_modem`
- `reset_wlan`
- `restart_service`
- `send_sms`
- `set_asset_id`
- `set_description`
- `set_log_level`
- `set_manual_apn`
- `set_name`
- `set_wan_device_bandwidth`
- `set_wan_device_default_connection_state`
- `set_wan_device_priority`
- `speed_test`
- `start_file_server`
- `start_packet_capture`
- `start_streaming_capture`
- `stop_monitor_log`
- `stop_monitor_sms`
- `stop_packet_capture`
- `stop_ping`
- `stop_speed_test`
- `traceroute_host`
- `unregister`
- `uptime`
- `wait_for_gps_fix`
- `wait_for_modem_connection`
- `wait_for_ntp`
- `wait_for_uptime`
- `wait_for_wan_connection`

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
- `unregister(eid: int = 0)` → `Dict[str, Any]`

## Device Information Methods

- `get_uptime()` → `int`
- `get_mac(format_with_colons: bool = False)` → `Optional[str]`
- `get_serial_number()` → `Optional[str]`
- `get_product_type()` → `Optional[str]`
- `get_name()` → `Optional[str]`
- `get_firmware_version(include_build_info: bool = False)` → `str`
- `get_router_model()` → `Optional[str]`

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
- `get_temperature(unit: str = 'fahrenheit')` → `Optional[float]`
- `get_power_usage(include_components: bool = True)` → `Optional[Dict[str, Any]]`
- `get_ncm_status(include_details: bool = False)` → `Optional[str]`
- `get_wan_devices_status()` → `Optional[Dict[str, Any]]`
- `get_signal_strength(uid: str, include_backlog: bool = False)` → `Optional[Dict[str, Any]]`
- `get_description()` → `Optional[Dict[str, Any]]`
- `get_asset_id()` → `Optional[Dict[str, Any]]`
- `set_description(description: str)` → `Optional[Dict[str, Any]]`
- `set_asset_id(asset_id: str)` → `Optional[Dict[str, Any]]`
- `set_name(name: str)` → `Optional[Dict[str, Any]]`

## Configuration Management Methods

### Appdata Management
- `get_appdata(name: str = '')` → `Optional[str]`
- `post_appdata(name: str = '', value: str = '')` → `None`
- `put_appdata(name: str = '', value: str = '')` → `None`
- `delete_appdata(name: str = '')` → `None`

### Certificate Management
- `get_ncm_api_keys()` → `Dict[str, Optional[str]]`
- `extract_cert_and_key(cert_name_or_uuid: str = '', return_filenames: bool = True, return_cert_content: bool = False, return_key_content: bool = False)` → `Union[Tuple[Optional[str], Optional[str]], Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]]`
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
- `get_wan_primary_device()` → `Optional[str]`

### Profile Configuration
- `set_wan_device_priority(device_id: str, new_priority: float)` → `bool`
- `make_wan_device_highest_priority(device_id: str)` → `bool`
- `enable_wan_device(device_id: str)` → `bool`
- `disable_wan_device(device_id: str)` → `bool`
- `set_wan_device_default_connection_state(device_id: str, connection_state: str)` → `bool`
- `set_wan_device_bandwidth(device_id: str, ingress_kbps: int = None, egress_kbps: int = None)` → `bool`
- `reorder_wan_profiles(device_priorities: Dict[str, float])` → `bool`

## APN Management Methods

### Manual APN Configuration
- `set_manual_apn(device_or_id: str, new_apn: str)` → `Optional[Dict[str, Any]]`
- `remove_manual_apn(device_or_id: str)` → `Optional[Dict[str, Any]]`

### Advanced APN Configuration
- `add_advanced_apn(carrier: str, apn: str)` → `Optional[Dict[str, Any]]`
- `delete_advanced_apn(carrier_or_apn: str)` → `Optional[Dict[str, Any]]`

## Network Testing Methods

### Connectivity Testing
- `ping_host(host: str, count: int = 4, timeout: float = 15.0, interval: float = 0.5, packet_size: int = 56, interface: str = None, bind_ip: bool = False)` → `Optional[Dict[str, Any]]`
- `traceroute_host(host: str, max_hops: int = 30, timeout: float = 5.0)` → `Optional[Dict[str, Any]]`
- `speed_test(host: str = "", interface: str = "", duration: int = 5, packet_size: int = 0, port: int = None, protocol: str = "tcp", direction: str = "both")` → `Optional[Dict[str, Any]]`
- `stop_speed_test()` → `Optional[Dict[str, Any]]`
- `network_connectivity_test(host: str = "8.8.8.8", port: int = 53, timeout: float = 5.0)` → `Optional[Dict[str, Any]]`
- `stop_ping()` → `Optional[Dict[str, Any]]`

### DNS Operations
- `dns_lookup(hostname: str, record_type: str = "A")` → `Optional[Dict[str, Any]]`
- `clear_dns_cache()` → `Optional[Dict[str, Any]]`

## Packet Capture Methods

### Capture Operations
- `start_packet_capture(interface: str = "any", filter: str = "", count: int = 20, timeout: int = 600, wifichannel: str = "", wifichannelwidth: str = "", wifiextrachannel: str = "", url: str = "")` → `Optional[Dict[str, Any]]`
- `stop_packet_capture()` → `Optional[Dict[str, Any]]`
- `get_packet_capture_status()` → `Optional[Dict[str, Any]]`
- `download_packet_capture(filename: str, local_path: str = None, capture_params: dict = None)` → `Optional[Dict[str, Any]]`
- `start_streaming_capture(interface: str = "any", filter: str = "", wifichannel: str = "", wifichannelwidth: str = "", wifiextrachannel: str = "", url: str = "")` → `Optional[Dict[str, Any]]`
- `get_available_interfaces()` → `Optional[Dict[str, Any]]`
- `packet_capture(iface: str = None, filter: str = "", count: int = 10, timeout: int = 10, save_directory: str = "captures", capture_user: str = "SDKTCPDUMP")` → `Optional[Dict[str, Any]]`

## File Server Methods

- `start_file_server(folder_path: str = "files", port: int = 8000, host: str = "0.0.0.0", title: str = "File Download")` → `Optional[Dict[str, Any]]`

## User Management Methods

- `create_user(username: str, password: str, group: str = "admin")` → `Optional[Dict[str, Any]]`
- `get_users()` → `Optional[Dict[str, Any]]`
- `delete_user(username: str)` → `Optional[Dict[str, Any]]`
- `ensure_user_exists(username: str, password: str, group: str = "admin")` → `Optional[Dict[str, Any]]`
- `ensure_fresh_user(username: str, group: str = "admin")` → `Optional[Dict[str, Any]]`

## GPIO Methods

- `get_gpio(gpio_name: GPIOType, router_model: Optional[str] = None, return_path: bool = False)` → `Optional[Union[Any, str]]`
- `get_all_gpios(router_model: Optional[str] = None)` → `Dict[str, Any]`
- `get_available_gpios(router_model: Optional[str] = None)` → `List[str]`
- `get_raw_gpios()` → `Optional[Dict[str, Any]]`

## Monitoring, SMS, and CLI Methods

- `monitor_log(pattern: str = None, callback: callable = None, follow: bool = True, max_lines: int = 0, timeout: int = 0)` → `Optional[Dict[str, Any]]`
- `stop_monitor_log(monitor_result: Dict[str, Any])` → `Optional[Dict[str, Any]]`
- `monitor_sms(callback: callable, timeout: int = 0)` → `Optional[Dict[str, Any]]`
- `stop_monitor_sms(monitor_result: Dict[str, Any])` → `Optional[Dict[str, Any]]`
- `send_sms(phone_number: str = None, message: str = None, port: str = None)` → `Optional[str]`
- `execute_cli(commands: Union[str, List[str]], timeout: int = 10, soft_timeout: int = 5, clean: bool = True)` → `Optional[str]`

## NCM and Identification Methods

- `get_ncm_router_id()` → `Optional[Dict[str, Any]]`
- `get_ncm_group_name()` → `Optional[Dict[str, Any]]`
- `get_ncm_account_name()` → `Optional[Dict[str, Any]]`

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

### APN Management
```python
import cp

# Manual APN configuration using WAN rule ID
result = cp.set_manual_apn("00000006-a81d-3590-93ca-8b1fcfeb8e14", "custom.apn")
if result['success']:
    print(f"Manual APN set successfully for rule {result['rule_id']}")

# Manual APN configuration using modem device name
result = cp.set_manual_apn("mdm-123456", "device.apn")
if result['success']:
    print(f"Manual APN set for device {result['device_id']}")

# Remove manual APN
result = cp.remove_manual_apn("mdm-123456")
if result['success']:
    print("Manual APN removed successfully")

# Advanced APN configuration
result = cp.add_advanced_apn("Verizon", "vzwinternet")
if result['success']:
    print(f"Advanced APN added: {result['carrier']} -> {result['apn']}")

# Remove advanced APN by carrier
result = cp.delete_advanced_apn("Verizon")
if result['success']:
    print(f"Removed {result['deleted_count']} advanced APN entries")

# Remove advanced APN by APN name
result = cp.delete_advanced_apn("vzwinternet")
if result['success']:
    print(f"Removed {result['deleted_count']} advanced APN entries")
```

### Network Testing
```python
import cp

# Ping a host
result = cp.ping_host("8.8.8.8", count=5)
if result:
    print(f"Ping successful: {result['packet_loss']}% loss")

# Traceroute
result = cp.traceroute_host("google.com", max_hops=15)
if result:
    print(f"Traceroute completed in {result['total_time']}ms")

# Speed test
result = cp.speed_test(host="speedtest.net", duration=10)
if result:
    print(f"Download: {result['download_speed']} Mbps")

# DNS lookup
result = cp.dns_lookup("google.com", "A")
if result:
    print(f"DNS resolution: {result['result']}")
```

### Packet Capture
```python
import cp

# Start packet capture
result = cp.start_packet_capture(interface="eth0", count=100, timeout=60)
if result['success']:
    print(f"Capture started: {result['filename']}")

# Check capture status
status = cp.get_packet_capture_status()
print(f"Capture status: {status['status']}")

# Download captured file
result = cp.download_packet_capture("capture.pcap", "/local/path/")
if result['success']:
    print("Capture file downloaded successfully")
```

This comprehensive list shows that the `cp` module provides extensive functionality for interacting with NCOS routers, including:

- **Status Monitoring**: System, network, GPS, and device status information
- **Network Operations**: WAN/LAN management, routing, firewall, and QoS
- **APN Management**: Manual and advanced APN configuration for cellular modems
- **Network Testing**: Ping, traceroute, speed tests, and connectivity testing
- **Packet Capture**: Advanced packet capture and analysis capabilities
- **System Control**: Device management, user administration, and service control
- **WAN Profile Management**: Device prioritization, bandwidth control, and connection management
- **Event Handling**: Real-time configuration change monitoring
- **GPIO Control**: Hardware interface management
- **File Operations**: File server and data management capabilities

The module provides a complete SDK for developing applications that interact with NCOS routers, from simple status queries to complex network management operations.
