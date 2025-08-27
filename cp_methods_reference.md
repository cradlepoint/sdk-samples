# CP Module Methods Reference

This document lists all available methods when importing the `cp` module for NCOS SDK applications.

## Core Communication Methods

### Basic CRUD Operations
- `get(base, query='', tree=0)` - Retrieve data from router tree
- `post(base, value='', query='')` - Send POST request to router tree
- `put(base, value='', query='', tree=0)` - Send PUT request to router tree
- `delete(base, query='')` - Send DELETE request to router tree
- `decrypt(base, query='', tree=0)` - Decrypt sensitive data

### Logging and Alerts
- `log(value='')` - Add log entry to system log
- `alert(value='')` - Send custom alert to NCM

## Event Handling Methods

- `register(action, path, callback, *args)` - Register callback for config store events
- `on(action, path, callback, *args)` - Alias for register
- `unregister(eid)` - Unregister callback by event ID

## Device Information Methods

- `get_uptime()` - Get router uptime in seconds
- `get_device_mac()` - Get device MAC address
- `get_device_serial_num()` - Get device serial number
- `get_device_product_type()` - Get device product type
- `get_device_name()` - Get device name
- `get_device_firmware()` - Get device firmware information

## Network Status Methods

### WAN/LAN Status
- `get_wan_status()` - Get WAN status and connection information
- `get_lan_status()` - Get LAN status and client information
- `get_wlan_status()` - Get wireless LAN status
- `get_connected_wans()` - Get list of connected WAN UIDs
- `get_sims()` - Get list of modem UIDs with SIMs

### Client Information
- `get_ipv4_wired_clients()` - Get IPv4 wired clients
- `get_ipv4_wifi_clients()` - Get IPv4 Wi-Fi clients
- `get_ipv4_lan_clients()` - Get all IPv4 clients (wired + Wi-Fi)

## GPS and Location Methods

- `get_gps_status()` - Get GPS status and fix information
- `get_lat_long()` - Get latitude and longitude as floats
- `dec(deg, min, sec)` - Convert degrees/minutes/seconds to decimal

## System Status Methods

- `get_system_resources(cpu=True, memory=True)` - Get system resource usage
- `get_temperature()` - Get device temperature
- `get_power_usage()` - Get power usage information
- `get_ncm_status()` - Get NCM connection status

## Configuration Management Methods

### Appdata Management
- `get_appdata(name)` - Get appdata value by name
- `post_appdata(name, value)` - Create appdata entry
- `put_appdata(name, value)` - Update appdata value
- `delete_appdata(name)` - Delete appdata entry

### Certificate Management
- `get_ncm_api_keys()` - Get NCM API keys
- `extract_cert_and_key(cert_name_or_uuid)` - Extract certificate and key files

## Wait/Utility Methods

- `wait_for_uptime(min_uptime_seconds)` - Wait for minimum uptime
- `wait_for_ntp(timeout=300, check_interval=1)` - Wait for NTP sync
- `wait_for_wan_connection(timeout=300)` - Wait for WAN connection
- `wait_for_modem_connection(timeout=300)` - Wait for modem connection
- `wait_for_gps_fix(timeout=300)` - Wait for GPS fix

## Control Methods

### Device Control
- `reboot_device()` - Reboot the device
- `factory_reset()` - Perform factory reset

### Network Control
- `reset_modem(modem_id=None)` - Reset modem(s)
- `reset_wlan()` - Reset WLAN configuration

### System Control
- `clear_logs()` - Clear system logs
- `restart_service(service_name)` - Restart system service
- `set_log_level(level)` - Set logging level

## Advanced Status Methods

- `get_wan_devices_status()` - Get detailed WAN device status
- `get_modem_status()` - Get cellular modem status
- `get_signal_strength()` - Get signal strength information
- `get_comprehensive_status()` - Get comprehensive system status


## Specialized Status Methods

- `get_openvpn_status()` - Get OpenVPN status
- `get_hotspot_status()` - Get hotspot status
- `get_obd_status()` - Get OBD status
- `get_qos_status()` - Get QoS status
- `get_firewall_status()` - Get firewall status
- `get_dns_status()` - Get DNS status
- `get_dhcp_status()` - Get DHCP status

## Specialized Helper Methods

### QoS Methods
- `get_qos_queues()` - Get QoS queue details
- `get_qos_queue_by_name(queue_name)` - Get specific QoS queue
- `get_qos_traffic_stats()` - Get QoS traffic statistics

### DHCP Methods
- `get_dhcp_clients_by_interface(interface_name)` - Get DHCP clients by interface
- `get_dhcp_clients_by_network(network_name)` - Get DHCP clients by network
- `get_dhcp_client_by_mac(mac_address)` - Get DHCP client by MAC
- `get_dhcp_client_by_ip(ip_address)` - Get DHCP client by IP
- `get_dhcp_interface_summary()` - Get DHCP interface summary

### Routing Methods
- `get_bgp_status()` - Get BGP status
- `get_ospf_status()` - Get OSPF status
- `get_static_routes()` - Get static routes
- `get_routing_policies()` - Get routing policies
- `get_routing_table_by_name(table_name)` - Get routing table by name
- `get_arp_table()` - Get ARP table
- `get_route_summary()` - Get routing summary

### Certificate Methods
- `get_certificates()` - Get certificates list
- `get_certificate_by_name(cert_name)` - Get certificate by name
- `get_certificate_by_uuid(cert_uuid)` - Get certificate by UUID
- `get_expiring_certificates(days_threshold=30)` - Get expiring certificates
- `get_certificate_summary()` - Get certificate summary

### Firewall Methods
- `get_firewall_connections()` - Get firewall connections
- `get_firewall_hitcounters()` - Get firewall hit counters
- `get_firewall_marks()` - Get firewall marks
- `get_firewall_state_timeouts()` - Get firewall timeouts
- `get_firewall_connections_by_protocol(protocol)` - Get connections by protocol
- `get_firewall_connections_by_ip(ip_address)` - Get connections by IP
- `get_firewall_summary()` - Get firewall summary

## WLAN Specialized Methods

### Client Management
- `get_wlan_clients()` - Get WLAN clients
- `get_wlan_client_count()` - Get WLAN client count
- `get_wlan_client_count_by_band()` - Get WLAN client count by band

### Radio Management
- `get_wlan_radio_status()` - Get WLAN radio status
- `get_wlan_radio_by_band(band)` - Get WLAN radio by band
- `get_wlan_channel_info(band=None)` - Get WLAN channel info

### Configuration and Events
- `get_wlan_events()` - Get WLAN events
- `get_wlan_region_config()` - Get WLAN region config
- `get_wlan_remote_status()` - Get WLAN remote status
- `get_wlan_state()` - Get WLAN state
- `get_wlan_trace()` - Get WLAN trace
- `get_wlan_debug()` - Get WLAN debug info

## Additional Status Methods

### Hardware Status
- `get_storage_status()` - Get storage status
- `get_usb_status()` - Get USB status
- `get_poe_status()` - Get PoE status
- `get_sensors_status()` - Get sensors status

### System Services Status
- `get_services_status()` - Get services status
- `get_apps_status()` - Get apps status
- `get_log_status()` - Get log status
- `get_event_status()` - Get event status

### Network Performance Status
- `get_network_throughput()` - Get network throughput
- `get_flow_statistics()` - Get flow statistics
- `get_client_usage()` - Get client usage
- `get_multicast_status()` - Get multicast status

### Advanced Network Status
- `get_vpn_status()` - Get VPN status
- `get_security_status()` - Get security status
- `get_iot_status()` - Get IoT status
- `get_sdwan_status()` - Get SD-WAN status

## Utility Methods

- `get_logger()` - Get logger instance for advanced logging
- `uptime()` - Get uptime (monkey patched version)

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


This comprehensive list shows that the `cp` module provides extensive functionality for interacting with NCOS routers, including status monitoring, network operations, and system control.
