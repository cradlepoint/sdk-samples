# app_template
Template for Ericsson Cradlepoint SDK Applications.  
- `app_template.py` - main app file, including examples of using the CPSDK library.  
- `csclient.py` - this library contains the `EventingCSClient` class, an extension of the `CSClient` class that includes event-driven functionality.  
- `cpsdk.py` - this library contains the `CPSDK` class, an extension of the `EventingCSClient` that provides easy-to-use methods for common use cases.
- `package.ini` - contains application metadata including vendor, notes, version and start flags.
- `start.sh` - shell script that starts the application.
- `readme.md` - detailed information about the application including any requirements or limitations.

## Usage

To use the `CPSDK` class, instantiate it with the application name and call the desired methods to interact with the router's configuration and status.  

### Quickstart:  
```python
from cpsdk import CPSDK
cp = CPSDK('My_App')
cp.log('Starting...')
```

# CPSDK Library Documentation

## Overview

The CPSDK (CradlePoint SDK) library is a Python-based SDK designed to interact with CradlePoint routers and network devices. It provides a comprehensive set of methods to manage, monitor, and configure router settings, network clients, certificates, and various system parameters.

### Purpose and Scope

This SDK is intended for developers building applications that need to:
- Monitor router status and system information
- Manage network clients (wired and wireless)
- Handle certificates and security configurations
- Access GPS location data
- Manage WAN connections and SIM cards
- Store and retrieve application-specific data

## Module Structure

The library consists of a single main class `CPSDK` that inherits from `EventingCSClient`, which in turn inherits from `CSClient`. All functionality is encapsulated within this class, providing a unified interface for router interactions.

## Function Details

### Core Functions

#### `__init__(appname)`
Initializes the CPSDK client.
- **Parameters:**
  - `appname` (str): Name of the application using the SDK
- **Returns:** None

#### `get_uptime()`
Retrieves the router's uptime.
- **Parameters:** None
- **Returns:** int (uptime in seconds)

#### `wait_for_uptime(min_uptime_seconds)`
Waits for the device to reach a minimum uptime.
- **Parameters:**
  - `min_uptime_seconds` (int): Minimum required uptime in seconds
- **Returns:** None
- **Side Effects:** May sleep the current thread

### Application Data Management

#### `get_appdata(name)`
Retrieves application data from NCOS Config.
- **Parameters:**
  - `name` (str): Name of the appdata to retrieve
- **Returns:** Any (value of the appdata) or None if not found

#### `post_appdata(name, value)`
Creates new appdata in NCOS Config.
- **Parameters:**
  - `name` (str): Name of the appdata
  - `value` (Any): Value to store
- **Returns:** None

#### `put_appdata(name, value)`
Updates existing appdata in NCOS Config.
- **Parameters:**
  - `name` (str): Name of the appdata
  - `value` (Any): New value
- **Returns:** None

#### `delete_appdata(name)`
Deletes appdata from NCOS Config.
- **Parameters:**
  - `name` (str): Name of the appdata to delete
- **Returns:** None

### Certificate Management

#### `extract_cert_and_key(cert_name_or_uuid)`
Extracts and saves certificates and keys to the local filesystem.
- **Parameters:**
  - `cert_name_or_uuid` (str): Name or UUID of the certificate
- **Returns:** tuple (str, str) - (certificate filename, key filename) or (None, None) if not found

### Network Client Management

#### `get_ipv4_wired_clients()`
Retrieves information about wired IPv4 clients.
- **Parameters:** None
- **Returns:** list of dicts containing client information

#### `get_ipv4_wifi_clients()`
Retrieves information about wireless IPv4 clients.
- **Parameters:** None
- **Returns:** list of dicts containing client information

#### `get_ipv4_lan_clients()`
Retrieves all IPv4 clients (both wired and wireless).
- **Parameters:** None
- **Returns:** dict containing wired and wireless clients

### Location and WAN Management

#### `get_lat_long()`
Retrieves GPS coordinates.
- **Parameters:** None
- **Returns:** tuple (float, float) - (latitude, longitude) or (None, None) if not available

#### `get_connected_wans()`
Retrieves list of connected WAN interfaces.
- **Parameters:** None
- **Returns:** list of WAN UIDs

#### `get_sims()`
Retrieves list of modems with active SIM cards.
- **Parameters:** None
- **Returns:** list of modem UIDs

### Inherited Methods from CSClient

#### `get(path)`
Retrieves data from the router's config store.
- **Parameters:**
  - `path` (str): Path to the data in the router's config store
- **Returns:** Any (the requested data)

#### `post(path, data)`
Posts data to the router's config store.
- **Parameters:**
  - `path` (str): Path where to store the data
  - `data` (Any): Data to store
- **Returns:** Any (response from the router)

#### `put(path, data)`
Updates data in the router's config store.
- **Parameters:**
  - `path` (str): Path to the data to update
  - `data` (Any): New data
- **Returns:** Any (response from the router)

#### `delete(path)`
Deletes data from the router's config store.
- **Parameters:**
  - `path` (str): Path to the data to delete
- **Returns:** Any (response from the router)

#### `decrypt(path)`
Decrypts encrypted data from the router's config store.
- **Parameters:**
  - `path` (str): Path to the encrypted data
- **Returns:** str (decrypted data)

#### `log(message)`
Logs a message to the router's system log.
- **Parameters:**
  - `message` (str): Message to log
- **Returns:** None

#### `alert(message)`
Constructs and sends a custom alert to NCM for the device. Apps calling this method must be running on the target device to send the alert. If invoked while running on a computer, then only a log is output.
- **Parameters:**
  - `message` (str): Text to be displayed in the alert
- **Returns:** 
  - Success: None
  - Failure: An error
- **Notes:** Only available when running on NCOS (Linux) devices. When running on a computer, it will only print the alert text.

### Inherited Methods from EventingCSClient

#### `start()`
Starts the event handling thread.
- **Parameters:** None
- **Returns:** None
- **Side Effects:** Starts a background thread for event handling

#### `stop()`
Stops the event handling thread.
- **Parameters:** None
- **Returns:** None
- **Side Effects:** Stops the background thread for event handling

#### `register(path, callback)`
Registers a callback function for events on a specific path.
- **Parameters:**
  - `path` (str): Path to monitor for events
  - `callback` (callable): Function to call when events occur
- **Returns:** None

#### `unregister(path)`
Unregisters event monitoring for a specific path.
- **Parameters:**
  - `path` (str): Path to stop monitoring
- **Returns:** None

## Usage Examples

### Basic Initialization
```python
from cpsdk import CPSDK

# Initialize the SDK
cp = CPSDK("MyApp")

# Get router uptime
uptime = cp.get_uptime()
cp.log(f"Router uptime: {uptime} seconds")
```

### Managing Application Data
```python
# Store application data
cp.post_appdata("my_setting", "value")

# Retrieve application data
value = cp.get_appdata("my_setting")
cp.log(f"Retrieved value: {value}")
```

### Network Client Monitoring
```python
# Get all network clients
clients = cp.get_ipv4_lan_clients()

# Log wired clients
for client in clients["wired_clients"]:
    cp.log(f"Wired client: {client['hostname']} ({client['ip']})")

# Log wireless clients
for client in clients["wifi_clients"]:
    cp.log(f"Wireless client: {client['hostname']} on {client['ssid']}")
```

### Certificate Management
```python
# Extract certificate and key
cert_file, key_file = cp.extract_cert_and_key("my_cert")
if cert_file and key_file:
    cp.log(f"Certificate saved as: {cert_file}")
    cp.log(f"Key saved as: {key_file}")
```

### Alert Example
```python
# Send an alert to NCM
cp.alert("Critical: System temperature exceeded threshold")

# The alert will only be sent when running on NCOS
# When running on a computer, it will only log the alert text
```
