# NCOS SDK and Sample Applications.

----------

This directory contains the NCOS SDK tools and sample applications. 

The Application Developers Guide is the best document to read first.

## Documentation

- **NCOS SDK Developers Guide**
    - **https://docs.cradlepoint.com/r/NCOS-SDK-Developers-Guide**

## Files

- **make.py**
    - The main python tool used to manage application paackages.  Supports actions: create, build, install, uninstall, start, stop, or purge from a locally connected device that is in DEV mode.
- **sdk_settings.ini**
    - This is the ini file that contains the settings used by python make.py.
- **tools/**
    - Contains support files for the SDK. There is also a simple python syslog server that can be used during application development.

## Sample Application Descriptions

- **5GSpeed**
    - Run Ookla speedtests via NCM API.  Results are put in asset_id field (configurable in SDK Data).  Clearing the results starts a new test.  This can be done easily via NCM API v2 /routers/ endpoint.
- **app_template**
    - A template for the creation of a new application utilizing the csclient library.
- **app_holder**
    - Just a holder for dynamic_app. See dynamic_app.
- **Autoinstall**
    - Automatically choose fastest SIM on install.  On bootup, AutoInstall detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization. Then the app collects diagnostics and runs Ookla speedtests on each SIM. Then the app prioritizes the SIMs WAN Profiles by TCP download speed.  Results are written to the log, set as the description field, and sent as a custom alert. The app can be manually triggered again by clearing out the description field in NCM.  
- **Installer_UI**
    - Provide a web interface for installers to configure WiFi and run speedtests.
- **Mobile_Site_Survey**
    - Robust Site Survey app with cloud aggregating and reporting via 5g-ready.io
- **app_template_csclient**
    - A template for the creation of a new application utilizing the csclient library.
- **cp_shell**
    - Web interface for running linux shell commands.
- **cli_sample**
    - Includes csterm module that enables access to local CLI to send commands and return output.
- **ipverify_custom_action**
    - Create a custom action in a function to be called when an IPverify test status changes.
- **dynamic_app**
    - Downloads apps from a self hosted url and install into app_holder app. Overcome limitates with dev_mode and app size limits.
- **cpu_usage**
    - Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
- **geofences**
    - Send alert when entering or exiting geofences.  Configure geofences in SDK app data after loading app.
- **gpio_any_wan_connected**
    - Set GPIO out high when any wan (not just modems) is connected.
- **gps_probe**
    - Probe the GPS hardware and log the results.
- **hello_world**
    - Outputs a 'Hello World!' log every 10 seconds.
- **hspt**
    - Sets up a custom Hot Spot landing page.
- **ibr1700_gnss**
    - Demonstrates how to access the gyroscope and accelerometer data on the IBR1700
- **ibr1700_obdII**
    - Demonstrates how to access OBD-II PIDs on the IBR1700
- **logfile**
    - Writes router logs to flash available for download via HTTP/LAN Manager.
- **mosquitto**
    - Demonstrates launching embedded mosquitto server
- **mqtt_app**
    - Demonstrated MQTT using the paho library
- **mqtt_azure_client**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central.
- **mqtt_azure_tls**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central over TLS connection.
- **OBDII_monitor**
    - Monitor OBD-II values, put latest values in asset_id, and alert on conditions defined in SDK AppData.
- **ping_sample**
    - Contains ping function and example usage.
- **ports_status**
    - Sets the device description to visually show the LAN/WAN/WWAN/Modem/IP Verify status.
- **python_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **rproxy**
    - A reverse proxy similar to port forwarding, except traffic forwarded to a
    udp/tcp target will be sourced from the router's IP. This reverse proxy can
    be dynamically added to clients as they connect. 
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
- **system_monitor**
    - Get various system diagnostics, alert on thresholds, and put current status in asset_id field.
- **tornado_sample**
	- A webserver using Tornado with NCM-themed example to set WiFi SSIDs.
- **throttle_cellular_datacap**
	-  Upon *any* Modem interface reaching 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit (minbwup and minbwdown variables).
- **throttle_cellular_datacap_rate_tiered**
	-  Upon *any* Modem interface reaching 70, 80, 90 or 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit as set by the rate tier (minbwup and minbwdown variables).

----------

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service (“TSLA”).

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER’S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED “AS-IS,” WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER’S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER’S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED  WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc.  All rights reserved.
