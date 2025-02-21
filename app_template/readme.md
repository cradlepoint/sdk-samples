# app_template
Template for Ericsson Cradlepoint SDK Applications.  
- `app_template.py` - main app file, including examples of using the CPSDK library.  
- `csclient.py` - this library contains the `EventingCSClient` class, an extension of the `CSClient` class that includes event-driven functionality.  
- `cpsdk.py` - this library contains the `CPSDK` class, an extension of the `EventingCSClient` that provides easy-to-use methods for common use cases.
- `package.ini` - contains application metadata including vendor, notes, version and start flags.
- `start.sh` - shell script that starts the application.
- `readme.md` - detailed information about the application including any requirements or limitations.

## Documentation

## Class: `CPSDK`

### Quickstart:  
```python
from cpsdk import CPSDK
cp = CPSDK('My_App')
cp.log('Starting...')
```

### Constructor

- **`__init__(self, appname)`**
  - Initializes the CPSDK instance with the given application name.
  - **Parameters:**
    - `appname` (str): The name of the application.

**Methods inherited from EventingCSClient:**

- **`get(self, path)`**
  - **Description:** Sends a GET request to the specified path.
  - **Parameters:**
    - `path` (str): The API endpoint path.
  - **Returns:** The response data from the GET request.

- **`post(self, path, data)`**
  - **Description:** Sends a POST request to the specified path with the given data.
  - **Parameters:**
    - `path` (str): The API endpoint path.
    - `data` (dict): The data to send in the POST request.

- **`put(self, path, data)`**
  - **Description:** Sends a PUT request to the specified path with the given data.
  - **Parameters:**
    - `path` (str): The API endpoint path.
    - `data` (dict): The data to send in the PUT request.

- **`delete(self, path)`**
  - **Description:** Sends a DELETE request to the specified path.
  - **Parameters:**
    - `path` (str): The API endpoint path.

- **`log(self, message)`**
  - **Description:** Logs a message.
  - **Parameters:**
    - `message` (str): The message to log.

- **`logger.exception(self, message)`**
  - **Description:** Logs an exception message.
  - **Parameters:**
    - `message` (str): The exception message to log.

- **`register(self, event_name, callback)`**
  - **Description:** Registers a callback function to be executed when a specific event occurs.
  - **Parameters:**
    - `event_name` (str): The name of the event to listen for.
    - `callback` (function): The function to call when the event occurs.
  - **Returns:** None

### Methods in CPSDK:

- **`get_uptime(self)`**
  - **Description:** Returns the router uptime in seconds.
  - **Returns:** `int` - The uptime in seconds.

- **`wait_for_uptime(self, min_uptime_seconds)`**
    - **Description:** Waits for the device uptime to be greater than the specified uptime and sleeps if it is less than the specified uptime.
    - **Parameters:**
        - `min_uptime_seconds` (int): The minimum uptime in seconds to wait for.

- **`get_appdata(self, name)`**
    - **Description:** Retrieves the value of app data from NCOS Config by name.
    - **Parameters:**
        - `name` (str): The name of the app data to retrieve.
    - **Returns:** The value of the app data or `None` if not found.

- **`post_appdata(self, name, value)`**
    - **Description:** Creates app data in NCOS Config by name.
    - **Parameters:**
        - `name` (str): The name of the app data to create.
        - `value` (str): The value of the app data to set.

- **`put_appdata(self, name, value)`**
    - **Description:** Sets the value of app data in NCOS Config by name.
    - **Parameters:**
        - `name` (str): The name of the app data to update.
        - `value` (str): The new value of the app data.

- **`delete_appdata(self, name)`**
    - **Description:** Deletes app data in NCOS Config by name.
    - **Parameters:**
        - `name` (str): The name of the app data to delete.

- **`extract_and_save_cert(self, cert_name)`**
    - **Description:** Extracts and saves the certificate and key to the local filesystem.
    - **Parameters:**
        - `cert_name` (str): The name of the certificate to extract and save.

- **`get_ipv4_wired_clients(self)`**
    - **Description:** Returns a list of IPv4 wired clients and their details.
    - **Returns:** `list` - A list of dictionaries containing client details.

- **`get_ipv4_wifi_clients(self)`**
    - **Description:** Returns a list of IPv4 Wi-Fi clients and their details.
    - **Returns:** `list` - A list of dictionaries containing client details.

- **`get_ipv4_lan_clients(self)`**
    - **Description:** Returns a dictionary containing all IPv4 clients, both wired and Wi-Fi.
    - **Returns:** `dict` - A dictionary with keys `wired_clients` and `wifi_clients`, each containing a list of client details.

## Dependencies

- The `CPSDK` class depends on the `EventingCSClient` class from the `csclient` module.
- The `time` module is used for sleeping operations.

## Usage

To use the `CPSDK` class, instantiate it with the application name and call the desired methods to interact with the router's configuration and status.

