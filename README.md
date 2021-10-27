# NCOS SDK and Sample Applications.

----------

This directory contains the NCOS SDK tools and sample applications. Below is a description of each. The Application Developmers Guide is the best document to read first.

## Documents

- **README.html**
    - This README file.
- **Cradlepoint NCOS SDK v3.1 Application Developers Guide.html**
    - The main document that describes application development.

## Sample Application Directories

- **app_template_csclient**
    - A template for the creation of a new application utilizing the csclient library.
- **Boot2**
    - On bootup, this application will perform a speedtest on each SIM and prioritize them based on TCP download.  Results are logged, sent as an alert, and PUT to NCM API "custom1" field.
- **cpu_usage**
    - Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
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
- **mosquitto**
    - Demonstrates launching embedded mosquitto server
- **mqtt_app**
    - Demonstrated MQTT using the paho library
- **mqtt_azure_client**
    - Sample Application which uses SDK to send sensor data to
Microsoft Azure IoT Central.
- **mqtt_azure_tls**
    - Sample Application which uses SDK to send sensor data to
Microsoft Azure IoT Central over TLS connection.
- **ping_sample**
    - Contains ping function and example usage.
- **python_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **send_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
- **serial_temp**
    - This is a test application to serial data from the data logger connected
to the router and output that to MQTT messages that are forwarded from the
router to Azure IoT Central.
- **serial_vibration_test**
    - This is a test developed for the Cradlepoint Serial Device (CSD) to be used during vibration testing of the CSD.  The application is a simple serial echo server that opens a port on the router.  Data is sent to the application and is echoed back to the client over the serial port.  A LAN device is connected and communicates with the router via port 5556.  When the vibration test is running, the LAN client will be notified if the serial cable is disconnected or connected.
- **simple_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **simple_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **tornado_sample**
	- A webserver using Tornado with NCM-themed example to set WiFi SSIDs.

## SDK Directories

- **built_apps/**
    - Ready to use sample apps - Download the .tar.gz file, then upload to your NetCloud Manager account and assign to groups.

- **tools**
    - Contains support files for the SDK. There is also a simple python syslog server that can be used during application development.

## Files

- **make.py**
    - The main python tool used to build application packages and install, uninstall, start, stop, or purge from a locally connected device that is in DEV mode.
- **sdk_settings.ini**
    - This is the ini file that contains the settings used by python make.py.

----------

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service (“TSLA”).

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER’S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED “AS-IS,” WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER’S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER’S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED  WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc.  All rights reserved.
