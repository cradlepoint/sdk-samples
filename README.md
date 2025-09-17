# Ericsson Cradlepoint NCOS SDK and Sample Applications.

## Documentation

- **NCOS SDK Developers Guide**
    - **https://docs.cradlepoint.com/r/NCOS-SDK-Developers-Guide**

## Built Apps

- **Pre-built Ready-to-Use Sample Applications can be downloaded here:**
    - **https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps**

## Files

- **cp.py**
    - The Python library used in applications to communicate with the router (NCOS).
- **cp_methods_reference.md**
    - Contains all available methods/functions when importing cp.py 
- **make.py**
    - The main python tool used to manage application paackages.  Supports actions: create, build, install, uninstall, start, stop, purge, and update from a locally connected device that is in DEV mode.
- **sdk_settings.ini**
    - This is the ini file that contains the settings used by python make.py.
- **tools/bin**
    - Contains pscp.exe for windows.

## Sample Application Descriptions

- **5GSpeed**
    - Run Ookla speedtests via NCM API.  Results are put in asset_id field (configurable in SDK Data).  Clearing the results starts a new test.  This can be done easily via NCM API v2 /routers/ endpoint.
- **Autoinstall**
    - Automatically choose fastest SIM on install.  On bootup, AutoInstall detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization. Then the app collects diagnostics and runs Ookla speedtests on each SIM. Then the app prioritizes the SIMs WAN Profiles by TCP download speed.  Results are written to the log, set as the description field, and sent as a custom alert. The app can be manually triggered again by clearing out the description field in NCM.  
- **Installer_UI**
    - Provide a web interface for installers to configure WiFi and run speedtests.
- **Mobile_Site_Survey**
    - Robust Site Survey app with cloud aggregating and reporting via 5g-ready.io
- **app_template**
    - A template for the creation of a new application utilizing the csclient library.
- **app_holder**
    - Just a holder for dynamic_app. See dynamic_app.
- **cli_sample**
    - Includes csterm module that enables access to local CLI to send commands and return output.
- **clients**
    - Puts the LAN clients in the asset_id field, or specify another field in SDK Appdata.
- **client_rssi_monitor**
    - Gets the mac address and rssi of connected wlan clients and puts them in the asset_id field.
- **cp_shell**
    - Web interface for running linux shell commands.
- **cpu_usage**
    - Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.
- **cs_explorer**
    - A web based application for exploring config store (CS) data. Runs on http://ROUTER_IP:9002 by default.
- **dead_reckoning**
    - Enables dead_reckoning for GPS send-to-server.
- **ddns**
    - Updates a dynamic DNS hostname with the IP address of the WAN device matching specified WAN profile.
- **dynamic_app**
    - Downloads apps from a self hosted url and install into app_holder app. Overcome limitates with dev_mode and app size limits.
- **daily_speedtest**
    - Runs an ookla speedtest daily at configured hours and put results to user defined field (asset_id).
- **encrypt_appdata**
    - Uses ECC encryption to automatically encrypt app data values that start with specific prefixes (`enc_`, `secret_`, `password_`, or `encrypt_`).
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
- **geofences**
    - Send alert when entering or exiting geofences.  Configure geofences in SDK app data after loading app.
- **gpio_any_wan_connected**
    - Set GPIO out high when any wan (not just modems) is connected.
- **gpio_sample**
    - Demonstrates GPIO (General Purpose Input/Output) functionality.
- **hello_world**
    - Outputs a 'Hello World!' log every 10 seconds.
- **hspt**
    - Sets up a custom Hot Spot landing page.
- **ibr1700_gnss**
    - Demonstrates how to access the gyroscope and accelerometer data on the IBR1700
- **ibr1700_obdII**
    - Demonstrates how to access OBD-II PIDs on the IBR1700
- **iperf3**
    - Downloads and runs iPerf3 to a user defined server and puts results in asset_id.  Clear the asset_id to run a new test.
- **ipverify_custom_action**
    - Create a custom action in a function to be called when an IPverify test status changes.
- **logfile**
    - Writes router logs to flash available for download via HTTP/LAN Manager.
- **mosquitto**
    - Demonstrates launching embedded mosquitto server
- **mqtt_app**
    - Demonstrated MQTT using the paho library
- **mqtt_app_tls**
    - MQTT over TLS - extracts certificates from NCOS and uses them for TLS connection.
- **mqtt_azure_client**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central.
- **mqtt_azure_tls**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central over TLS connection.
- **ncx_self_provision**
    - Script and accompanying SDK application to allow devices to 'sef-provision' to an NCX/SASE network.
- **OBDII_monitor**
    - Monitor OBD-II values, put latest values in asset_id, and alert on conditions defined in SDK AppData.
- **ping_sample**
    - Contains ping function and example usage.
- **ports_status**
    - Sets the device description to visually show the LAN/WAN/WWAN/Modem/IP Verify status.
- **power_alert**
    - Sends alerts when external power is lost and restored.
- **python_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **rate_limit**
    - Enable QoS rule 1 until datacap alert is met then toggle to rule 2.
- **rproxy**
    - A reverse proxy similar to port forwarding, except traffic forwarded to a
    udp/tcp target will be sourced from the router's IP. This reverse proxy can
    be dynamically added to clients as they connect. 
- **s400_userio**
    - Provides example how to control the user IO on the S400.
- **shell_sample**
    - Provides example how to execute commands at OS shell: "ls - al".
- **send_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
- **serial_temp**
    - This is a test application to serial data from the data logger connected.
- **serial_vibration_test**
    - This is a test developed for the Cradlepoint Serial Device (CSD) to be used during vibration testing of the CSD.  The application is a simple serial echo server that opens a port on the router.  Data is sent to the application and is echoed back to the client over the serial port.  A LAN device is connected and communicates with the router via port 5556.  When the vibration test is running, the LAN client will be notified if the serial cable is disconnected or connected.
- **simple_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **simple_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **splunk_conntrack**
    - This app tails the conntrack table and sends new connections to Splunk.
- **splunk_log_filter**
    - This app tails /var/log/messages and sends filtered lines to Splunk.
- **system_monitor**
    - Get various system diagnostics, alert on thresholds, and put current status in asset_id field.
- **system_monitor_web**
    - A comprehensive real-time system monitoring application for Cradlepoint routers that tracks both memory and CPU usage with customizable alert thresholds and a professional web interface.
- **tailscale**
    - A 3rd party mesh VPN called  [Tailscale](https://tailscale.com) that makes it easy to connect your devices, wherever they are. This application provides a way to proxy traffic from the LAN to the Tailscale network. See the README.md for more information.
- **timezone_via_gnss**
	- An app to read the device's GNSS data and send a request to timezonedb.com in order to return and set time device's timezone.
- **tornado_sample**
	- A webserver using Tornado with NCM-themed example to set WiFi SSIDs.
- **throttle_cellular_datacap**
	-  Upon *any* Modem interface reaching 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit (minbwup and minbwdown variables).
- **throttle_cellular_datacap_rate_tiered**
	-  Upon *any* Modem interface reaching 70, 80, 90 or 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit as set by the rate tier (minbwup and minbwdown variables).
- **tunnel_modem_reset**
	- Monitor tunnels and if down, reset modem it egresses from.
- **usb_alerts**
	- Send alerts when USB devices are connected or disconnected.

----------

## `cp.py` Usage Example

To use the library, import the `cp` module and call the desired functions.

See the [cp_methods_reference](https://github.com/cradlepoint/sdk-samples/blob/master/cp_methods_reference.md) for a list of available methods/functions in cp.py.

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

----------

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service (“TSLA”).

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER’S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED “AS-IS,” WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER’S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER’S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED  WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc.  All rights reserved.
