# Ericsson Cradlepoint NCOS SDK

**Extend your Ericsson routers with custom Python applications.**

The NCOS SDK enables developers to build and deploy Python applications that run directly on Ericsson Cradlepoint NetCloud OS (NCOS) routers. Create custom logic for connectivity management, IoT data collection, monitoring, automation, and more—without replacing hardware.

---

## Why Custom Applications on Ericsson Routers?

- **Extend without hardware changes** — Add new capabilities through software while your existing Ericsson/Cradlepoint fleet stays in place.
- **Access router internals** — Query modem signal strength, WAN status, GPS, connected clients, and system metrics via a Python API.
- **Integrate with your stack** — Push data to cloud platforms (Azure IoT, Splunk, MQTT), trigger alerts, or automate workflows based on router state.
- **Deploy at scale** — Build once, distribute via NetCloud Manager to thousands of devices with group-based assignment.
- **Standard Python** — Use familiar libraries and patterns; the SDK provides a simple `cp` module for router interaction.

---

## Resources

| Resource | Link |
|----------|------|
| **Pre-built sample apps** | [Releases — built_apps](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps) |
| **NCOS SDK Developers Guide** | [Documentation](https://docs.cradlepoint.com/r/NCOS-SDK-Developers_Guide) |
| **NetCloud Manager — SDK apps** | [Tools Tab](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab) |

---

## Sample Applications

Ready-to-use applications you can install from the [releases page](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps). Each app includes source code for reference and customization.

### Application Catalog

## Sample Application Descriptions

- **5GSpeed**
    - Run Ookla speedtests via NCM API. Results are put in asset_id field (configurable in SDK Data). Clearing the results starts a new test. This can be done easily via NCM API v2 /routers/ endpoint.
    - **Download:** [5GSpeed v0.2.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/5GSpeed.v0.2.0.tar.gz)
- **Autoinstall**
    - Automatically choose fastest SIM on install. On bootup, AutoInstall detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization. Then the app collects diagnostics and runs Ookla speedtests on each SIM. Then the app prioritizes the SIMs WAN Profiles by TCP download speed. Results are written to the log, set as the description field, and sent as a custom alert. The app can be manually triggered again by clearing out the description field in NCM.
    - **Download:** [AutoInstall v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/AutoInstall.v1.0.0.tar.gz)
- **Installer_UI**
    - Provide a web interface for installers to configure WiFi and run speedtests.
    - **Download:** [Installer_UI v1.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/Installer_UI.v1.1.0.tar.gz)
- **Mobile_Site_Survey**
    - Field survey tool that runs speedtests and collects modem diagnostics with GPS locations, uploading results for network coverage and throughput analysis to 5g-ready.io
    - **Download:** [Mobile_Site_Survey v3.0.2.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/Mobile_Site_Survey.v3.0.2.tar.gz)
- **Motorola**
    - Integrates with Motorola SmartConnect by broadcasting WAN and VPN status as UDP beacons on configured LANs.
    - **Download:** [Motorola v1.2.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/Motorola.v1.2.0.tar.gz)
- **app_template**
    - A template for the creation of a new application utilizing the csclient library.
    - **Download:** [app_template v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/app_template.v1.0.0.tar.gz)
- **app_holder**
    - Just a holder for dynamic_app. See dynamic_app.
    - **Download:** [app_holder v1.0.3.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/app_holder.v1.0.3.tar.gz)
- **cli_sample**
    - Includes csterm module that enables access to local CLI to send commands and return output.
    - **Download:** [cli_sample v1.0.3.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/cli_sample.v1.0.3.tar.gz)
- **clients**
    - Puts the LAN clients in the asset_id field, or specify another field in SDK Appdata.
    - **Download:** [clients v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/clients.v1.0.0.tar.gz)
- **client_rssi_monitor**
    - Gets the mac address and rssi of connected wlan clients and puts them in the asset_id field.
    - **Download:** [client_rssi_monitor v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/client_rssi_monitor.v1.0.0.tar.gz)
- **cp_shell**
    - Web interface for running linux shell commands.
    - **Download:** [cp_shell v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/cp_shell.v0.1.0.tar.gz)
- **cpu_usage**
    - Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.
    - **Download:** [cpu_usage v0.2.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/cpu_usage.v0.2.0.tar.gz)
- **cs_explorer**
    - A web based application for exploring config store (CS) data. Runs on http://ROUTER_IP:9002 by default.
    - **Download:** [cs_explorer v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/cs_explorer.v1.0.0.tar.gz)
- **dead_reckoning**
    - Enables dead_reckoning for GPS send-to-server.
    - **Download:** [dead_reckoning v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/dead_reckoning.v1.0.0.tar.gz)
- **ddns**
    - Updates a dynamic DNS hostname with the IP address of the WAN device matching specified WAN profile.
    - **Download:** [ddns v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ddns.v1.0.0.tar.gz)
- **dynamic_app**
    - Downloads apps from a self hosted url and install into app_holder app. Overcome limitates with dev_mode and app size limits.
    - **Download:** [dynamic_app v1.0.3.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/dynamic_app.v1.0.3.tar.gz)
- **daily_speedtest**
    - Runs an ookla speedtest daily at configured hours and put results to user defined field (asset_id).
    - **Download:** [daily_speedtest v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/daily_speedtest.v1.0.0.tar.gz)
- **encrypt_appdata**
    - Uses ECC encryption to automatically encrypt app data values that start with specific prefixes (`enc_`, `secret_`, `password_`, or `encrypt_`).
    - **Download:** [encrypt_appdata v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/encrypt_appdata.v1.0.0.tar.gz)
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
    - **Download:** [ftp_client v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ftp_client.v2.0.0.tar.gz)
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
    - **Download:** [ftp_server v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ftp_server.v2.0.0.tar.gz)
- **geofences**
    - Send alert when entering or exiting geofences. Configure geofences in SDK app data after loading app.
    - **Download:** [geofences v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/geofences.v1.0.0.tar.gz)
- **gpio_any_wan_connected**
    - Set GPIO out high when any wan (not just modems) is connected.
    - **Download:** [gpio_any_wan_connected v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/gpio_any_wan_connected.v0.1.0.tar.gz)
- **gpio_sample**
    - Demonstrates GPIO (General Purpose Input/Output) functionality.
    - **Download:** [gpio_sample v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/gpio_sample.v1.0.0.tar.gz)
- **gpio_wlan_control**
    - Monitors the GPIO connector input and sets `control/wlan/enabled` to match the GPIO value.
    - **Download:** [gpio_wlan_control v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/gpio_wlan_control.v1.0.0.tar.gz)
- **hello_world**
    - Outputs a 'Hello World!' log every 10 seconds.
    - **Download:** [hello_world v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/hello_world.v1.0.0.tar.gz)
- **hspt**
    - Sets up a custom Hot Spot landing page.
    - **Download:** [hspt v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/hspt.v2.0.0.tar.gz)
- **ibr1700_gnss**
    - Demonstrates how to access the gyroscope and accelerometer data on the IBR1700
    - **Download:** [ibr1700_gnss v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ibr1700_gnss.v2.0.0.tar.gz)
- **ibr1700_obdII**
    - Demonstrates how to access OBD-II PIDs on the IBR1700
    - **Download:** [ibr1700_obdII v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ibr1700_obdII.v2.0.0.tar.gz)
- **iperf3**
    - Downloads and runs iPerf3 to a user defined server and puts results in asset_id. Clear the asset_id to run a new test.
    - **Download:** [iperf3 v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/iperf3.v1.0.0.tar.gz)
- **ipverify_custom_action**
    - Create a custom action in a function to be called when an IPverify test status changes.
    - **Download:** [ipverify_custom_action v1.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ipverify_custom_action.v1.1.0.tar.gz)
- **logfile**
    - Writes router logs to flash available for download via HTTP/LAN Manager.
    - **Download:** [logfile v0.4.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/logfile.v0.4.0.tar.gz)
- **mosquitto**
    - Demonstrates launching embedded mosquitto server
    - **Download:** [mosquitto v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mosquitto.v1.0.0.tar.gz)
- **mqtt_app**
    - Demonstrated MQTT using the paho library
    - **Download:** [mqtt_app v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mqtt_app.v2.0.0.tar.gz)
- **mqtt_app_tls**
    - MQTT over TLS - extracts certificates from NCOS and uses them for TLS connection.
    - **Download:** [mqtt_app_tls v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mqtt_app_tls.v1.0.0.tar.gz)
- **mqtt_azure_client**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central.
    - **Download:** [mqtt_azure_client v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mqtt_azure_client.v2.0.0.tar.gz)
- **mqtt_azure_tls**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central over TLS connection.
    - **Download:** [mqtt_azure_tls v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mqtt_azure_tls.v2.0.0.tar.gz)
- **ncx_self_provision**
    - Script and accompanying SDK application to allow devices to 'sef-provision' to an NCX/SASE network.
    - **Download:** [ncx_self_provision v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ncx_self_provision.v1.0.0.tar.gz)
- **OBDII_monitor**
    - Monitor OBD-II values, put latest values in asset_id, and alert on conditions defined in SDK AppData.
    - **Download:** [OBDII_monitor v1.0.2.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/OBDII_monitor.v1.0.2.tar.gz)
- **ping_sample**
    - Contains ping function and example usage.
    - **Download:** [ping_sample v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ping_sample.v1.0.0.tar.gz)
- **ports_status**
    - Sets the device description to visually show the LAN/WAN/WWAN/Modem/IP Verify status.
    - **Download:** [ports_status v1.31.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ports_status.v1.31.0.tar.gz)
- **power_alert**
    - Sends alerts when external power is lost and restored.
    - **Download:** [power_alert v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/power_alert.v0.1.0.tar.gz)
- **power_dashboard**
    - A comprehensive real-time power usage monitoring application for Cradlepoint routers that tracks current, total energy consumption, and voltage with a professional web interface. Optional power indicator message in asset ID.
    - **Download:** [power_dashboard v1.4.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/power_dashboard.v1.4.0.tar.gz)
- **python_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
    - **Download:** [python_module_list v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/python_module_list.v2.0.0.tar.gz)
- **rate_limit**
    - Enable QoS rule 1 until datacap alert is met then toggle to rule 2.
    - **Download:** [rate_limit v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/rate_limit.v1.0.0.tar.gz)
- **rproxy**
    - A reverse proxy similar to port forwarding, except traffic forwarded to a udp/tcp target will be sourced from the router's IP. This reverse proxy can be dynamically added to clients as they connect.
    - **Download:** [rproxy v0.0.15.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/rproxy.v0.0.15.tar.gz)
- **s400_userio**
    - Provides example how to control the user IO on the S400.
    - **Download:** [s400_userio v0.2.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/s400_userio.v0.2.0.tar.gz)
- **shell_sample**
    - Provides example how to execute commands at OS shell: "ls - al".
    - **Download:** [shell_sample v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/shell_sample.v0.1.0.tar.gz)
- **send_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
    - **Download:** [send_to_server v2.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/send_to_server.v2.1.0.tar.gz)
- **serial_temp**
    - This is a test application to serial data from the data logger connected.
    - **Download:** [serial_temp v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/serial_temp.v2.0.0.tar.gz)
- **serial_vibration_test**
    - This is a test developed for the Cradlepoint Serial Device (CSD) to be used during vibration testing of the CSD. The application is a simple serial echo server that opens a port on the router. Data is sent to the application and is echoed back to the client over the serial port. A LAN device is connected and communicates with the router via port 5556. When the vibration test is running, the LAN client will be notified if the serial cable is disconnected or connected.
- **signal_alert**
    - Monitors modem signal metrics on all connected modems and sends NetCloud alerts with GPS when any metric goes below its threshold. Sends one alert when signal crosses below and one when it recovers (after 60 seconds above threshold).
    - **Download:** [signal_alert v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/signal_alert.v0.1.0.tar.gz)
- **simple_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
    - **Download:** [simple_custom_dashboard v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/simple_custom_dashboard.v2.0.0.tar.gz)
- **simple_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
    - **Download:** [simple_web_server v2.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/simple_web_server.v2.0.0.tar.gz)
- **splunk_conntrack**
    - This app tails the conntrack table and sends new connections to Splunk.
    - **Download:** [splunk_conntrack v1.1.1.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/splunk_conntrack.v1.1.1.tar.gz)
- **splunk_log_filter**
    - This app tails /var/log/messages and sends filtered lines to Splunk.
    - **Download:** [splunk_log_filter v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/splunk_log_filter.v1.0.0.tar.gz)
- **system_monitor**
    - Get various system diagnostics, alert on thresholds, and put current status in asset_id field.
    - **Download:** [system_monitor v0.2.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/system_monitor.v0.2.0.tar.gz)
- **system_monitor_web**
    - A comprehensive real-time system monitoring application for Cradlepoint routers that tracks both memory and CPU usage with customizable alert thresholds and a professional web interface.
    - **Download:** [system_monitor_web v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/system_monitor_web.v1.0.0.tar.gz)
- **tailscale**
    - A 3rd party mesh VPN called [Tailscale](https://tailscale.com) that makes it easy to connect your devices, wherever they are. This application provides a way to proxy traffic from the LAN to the Tailscale network. See the README.md for more information.
    - **Download:** [tailscale v0.0.36.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/tailscale.v0.0.36.tar.gz)
- **timezone_via_gnss**
    - An app to read the device's GNSS data and send a request to timezonedb.com in order to return and set time device's timezone.
    - **Download:** [timezone_via_gnss v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/timezone_via_gnss.v0.1.0.tar.gz)
- **tornado_sample**
    - A webserver using Tornado with NCM-themed example to set WiFi SSIDs.
    - **Download:** [tornado_sample v0.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/tornado_sample.v0.1.0.tar.gz)
- **throttle_cellular_datacap**
    - Upon *any* Modem interface reaching 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit (minbwup and minbwdown variables).
    - **Download:** [throttle_cellular_datacap v1.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/throttle_cellular_datacap.v1.1.0.tar.gz)
- **throttle_cellular_datacap_rate_tiered**
    - Upon *any* Modem interface reaching 70, 80, 90 or 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit as set by the rate tier (minbwup and minbwdown variables).
    - **Download:** [throttle_cellular_datacap_rate_tiered v1.1.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/throttle_cellular_datacap_rate_tiered.v1.1.0.tar.gz)
- **tunnel_modem_reset**
    - Monitor tunnels and if down, reset modem it egresses from.
    - **Download:** [tunnel_modem_reset v1.0.4.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/tunnel_modem_reset.v1.0.4.tar.gz)
- **usb_alerts**
    - Send alerts when USB devices are connected or disconnected.
    - **Download:** [usb_alerts v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/usb_alerts.v1.0.0.tar.gz)
- **wan_dashboard**
    - Live WAN interface utilization graphs in a web page. Includes cumulative graph.
    - **Download:** [wan_dashboard v1.3.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/wan_dashboard.v1.3.0.tar.gz)
- **wan_rate**
    - Tracks WAN bandwidth rates over time and stores rolling averages in a configurable field.
    - **Download:** [wan_rate v1.0.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/wan_rate.v1.0.0.tar.gz)
- **wan_ip_change_alert**
    - Tracks the WAN IP address and sends an alert when it changes. Includes a confirmation delay to prevent false alerts from temporary IP changes.

    - **Download:** [wan_ip_change_alert v1.4.0.tar.gz](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/wan_ip_change_alert.v1.4.0.tar.gz)
----------

---

## Quick Start — make.py

The `make.py` tool manages the full lifecycle of SDK applications: create, build, install, and maintain.

### Usage

```bash
python make.py <action> [app_name]
```

### Actions

| Action | Description |
|--------|-------------|
| **create** | Create a new application from the `app_template` directory. Example: `python3 make.py create my_new_app` |
| **build** | Produce a distributable application archive (`.tar.gz`). Use `all` to build every app. |
| **install** | Securely copy the built archive to a locally connected NCOS device (requires SDK DEV mode). |
| **status** | Retrieve and print the current status of the app on the device. |
| **uninstall** | Remove the application from the locally connected NCOS device. |
| **purge** | Remove all installed applications from the device. |
| **update** | Update core SDK helper files (`cp.py`, `cp_methods_reference.md`, `make.py`, etc.) from the upstream repository. |

### Examples

```bash
# Create a new app
python3 make.py create my_new_app

# Build a single app
python3 make.py build my_new_app

# Build all apps
python3 make.py build all

# Clean artifacts for all apps
python3 make.py clean all
```

### Prerequisites

- **Python 3** is required.
- **SSH access** (scp/ssh) to the target NCOS device is required for `install`, `start`, `stop`, `uninstall`, `purge`, and `status`.
- The NCOS device must be in **SDK DEV mode** via registration and licensing with NetCloud Manager.
- Any directory containing a `package.ini` file is treated as an application.
- Run `python3 make.py help` for full help from the tool.

---

## Key Files

| File | Description |
|------|-------------|
| **cp.py** | The Python library used in applications to communicate with the router (NCOS). |
| **cp_methods_reference.md** | Reference for all available methods/functions when importing `cp.py`. |
| **make.py** | The main tool for managing application packages: create, build, install, uninstall, start, stop, purge, and update. |
| **sdk_settings.ini** | Configuration settings used by `make.py` (device connection, app name, etc.). |
| **tools/bin** | Contains `pscp.exe` for Windows-based transfers. |

---

## Code Example

```python
import cp

# Get router uptime
uptime = cp.get_uptime()
cp.log(f"Router uptime: {uptime} seconds")

# Get connected clients
clients = cp.get_ipv4_lan_clients()
cp.log(f"Total clients: {len(clients)}")

# Get device location
lat_long = cp.get_lat_long()
if lat_long:
    cp.log(f"Device location: {lat_long}")

# Get connected WANs
wans = cp.get_connected_wans()
cp.log(f"Connected WANs: {len(wans)}")

# Get SIM information
sims = cp.get_sims()
cp.log(f"SIM details: {sims}")
```

See the [cp_methods_reference](https://github.com/cradlepoint/sdk-samples/blob/master/cp_methods_reference.md) for the full API.

---

## License

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service ("TSLA").

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER'S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED "AS-IS," WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER'S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER'S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc. All rights reserved.





