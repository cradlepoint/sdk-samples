> # Update your app_template!
> ### Download [app_template.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/app_template.tar.gz)
> ### Extract it over the top of your existing app_template/ in your sdk-samples folder.

# Documentation

`app_template` is a template for creating Ericsson Cradlepoint SDK Applications

## File Descriptions

*   **`app_template.py`**: The main application file. This is where you will write the primary logic for your SDK application. It utilizes the `cp.py` library to interact with the router.
*   **`cp.py`**: A comprehensive helper library that simplifies interaction with the Cradlepoint router's NCOS. It provides functions for common tasks such as retrieving system information, managing network clients, and handling application data.
*   **`start.sh`**: The execution script for the application. This script is run by the router to start your application. It uses `cppython` to run the `app_template.py` script.
*   **`package.ini`**: A configuration file for your application. It is used to store settings, such as the application name, which is used by the `cp.py` library for logging.
*   **`readme.md`**: This documentation file. It provides an overview of the template and detailed documentation for the `cp.py` library.


## `cp.py` Usage Example

To use the library, import the `cp` module and call the desired functions.

```python
# import the SDK library
import cp

# Get router uptime
uptime = cp.get_uptime()
cp.log(f"Router uptime: {uptime} seconds")

# Get connected clients
clients = cp.get_ipv4_lan_clients()
cp.log(f"Total clients: {len(clients)}")
cp.log(f"Client details: {clients}")

# Get device location
lat_long = cp.get_lat_long()
if lat_long:
    cp.log(f"Device location: {lat_long}")

# Get connected WANs
wans = cp.get_connected_wans()
cp.log(f"Connected WANs: {len(wans)}")
cp.log(f"WAN details: {wans}")

# Get SIM information
sims = cp.get_sims()
cp.log(f"SIM cards: {len(sims)}")
cp.log(f"SIM details: {sims}")
```

## Function Reference

### Core Functions

These functions provide direct access to the router's configuration store (CS).

- **`get(base, query='', tree=0)`**: Retrieves data from the router's config store.
- **`post(base, value='', query='')`**: Posts new data to the router's config store.
- **`put(base, value='', query='', tree=0)`**: Updates existing data in the router's config store.
- **`delete(base, query='')`**: Deletes data from the router's config store.
- **`decrypt(base, query='', tree=0)`**: Retrieves and decrypts a value from the router's config store.

### System & Status

- **`get_uptime()`**: Returns the router uptime in seconds.
- **`wait_for_uptime(min_uptime_seconds)`**: Pauses execution until the router's uptime is greater than the specified value.
- **`wait_for_wan_connection(timeout=300)`**: Pauses execution until a WAN connection is established and returns true, or timeout is reached and returns false.
- **`get_lat_long()`**: Returns the latitude and longitude from the router's GPS.

### Application Data

- **`get_appdata(name)`**: Gets the value of a stored application data variable by name.
- **`post_appdata(name, value)`**: Creates a new application data variable.
- **`put_appdata(name, value)`**: Updates the value of an existing application data variable.
- **`delete_appdata(name)`**: Deletes an application data variable by name.

### Network Clients

- **`get_ipv4_wired_clients()`**: Returns a list of connected IPv4 wired clients and their details.
- **`get_ipv4_wifi_clients()`**: Returns a list of connected IPv4 Wi-Fi clients and their details.
- **`get_ipv4_lan_clients()`**: Returns a dictionary containing all wired and Wi-Fi IPv4 clients.

### WAN & SIMs

- **`get_connected_wans()`**: Returns a list of connected WAN interface UIDs.
- **`get_sims()`**: Returns a list of modem UIDs that have a SIM card present.

### Certificate Management

- **`get_ncm_api_keys()`**: Returns a dictionary of NCM API keys stored on the router.
- **`extract_cert_and_key(cert_name_or_uuid)`**: Extracts a certificate and its private key, saving them to local `.pem` files.

### Logging and Alerts

- **`log(value='')`**: Writes a message to the router's system log.
- **`alert(value='')`**: Sends a custom alert to NCM for the device.
- **`get_logger()`**: Returns the logger instance for more advanced logging control.

### Event Handling

- **`register(action, path, callback, *args)`**: Registers a callback function to be executed on a specified config store event.
- **`unregister(eid)`**: Removes a registered event callback by its ID. 
