# NCOS SDK/App sample Design Tools.
----------
This directory contains the NCOS SDK tools and sample applications. Below is a description of each. The Router Applications Development Guide is the best document to read first.

## Documents 

- **README.html**
    - This README file.
- **Router\_Application\_Development_Guide.html**
    - The main document that describes application development.
- **Router\_APIs\_for_Applications.html**
    - The router config store API in the router.

## Sample Application Directories 

- **app_template**
    - A skeleton template for the creation of a new application.
- **Boot1**
    - On bootup, this application will select test the connection of each sim in a dual sim modem and enable the best.
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
- **ibr1700_obdII**
    - Demonstrates how to access OBD-II PIDs on the IBR1700
- **mqtt_app**
    - Demonstrated MQTT using the paho library
- **ping**
    - Ping an address and log the results.
- **python\_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **send\_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
- **simple\_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **simple\_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.




## SDK Directories 

- **tools**
    - Contains support files for the SDK. There is also a simple python syslog server that can be used during application development.

## Files 

- **make.py**
    - The main python tool used to build application packages and install, uninstall, start, stop, or purge from a locally connected device that is in DEV mode.
- **sdk_settings.ini**
    - This is the ini file that contains the settings used by python make.py.




