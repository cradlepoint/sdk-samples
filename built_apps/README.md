# Built Apps
These files are sample SDK Applications that are ready to use for testing and do not require modification or "building" of the app from source files.  

## How to use these files: ##
Download the .tar.gz file, then upload to your NetCloud Manager account and assign to groups.

Additional documentation:
https://customer.cradlepoint.com/s/article/NetCloud-Manager-Tools-Tab#sdk_apps

----------

## App Descriptions ##

- **Autoinstall**
    - Automatically choose fastest SIM on install.  On bootup, AutoInstall detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization. Then the app collects diagnostics and runs Ookla speedtests on each SIM. Then the app prioritizes the SIMs WAN Profiles by TCP download speed.  Results are written to the log, set as the description field, and sent as a custom alert. The app can be manually triggered again by clearing out the description field in NCM.  
- **Boot2**
    - On bootup, this application will perform a speedtest on each SIM and prioritize them based on TCP download.  Results are logged, sent as an alert, and PUT to NCM API "custom1" field.
- **Mobile_Site_Survey**
    - Robust Site Survey app with cloud aggregating and reporting via 5g-ready.io
- **cp_shell_**
    - Web interface for running linux shell commands.
- **cpu_usage**
    - Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
- **geofences**
    - Send alert when entering or exiting configured geofences.
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
    - Writes router logs to flash available for download via HTTP/NCM LAN Manager port 8000.
- **mosquitto**
    - Demonstrates launching embedded mosquitto server
- **mqtt_app**
    - Demonstrated MQTT using the paho library
- **mqtt_azure_client**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central.
- **mqtt_azure_tls**
    - Sample Application which uses SDK to send sensor data to Microsoft Azure IoT Central over TLS connection.
- **ping_sample**
    - Contains ping function and example usage.
- **ports_status**
    - Sets the device description to visually show the LAN/WAN/WWAN/Modem/IP Verify status
- **python_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **send_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
- **simple_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **simple_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **system_monitor**
    - Get various system diagnostics, alert on thresholds, and put current status in asset_id field.
- **tornado_sample**
	- A webserver using Tornado with NCM-themed example to set WiFi SSIDs.


----------

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service (“TSLA”).

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER’S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED “AS-IS,” WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER’S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER’S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED  WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc.  All rights reserved.
