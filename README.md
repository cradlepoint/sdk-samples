# NCOS SDK/App sample Design Tools.
----------
This directory contains the NCOS SDK tools and sample applications. Below is a description of each. The Router Applications Development Guide is the best document to read first.

## *** IMPORTANT - PLEASE READ ***

This is version 2.0 of the NCOS SDK and applications. The SDK has been simplified from the previous SDK to decrease the learning curve to allow more focus on application development. The NCOS application infrastructure and packaging is unchanged. That is, an 'tar.gz' application package built with the previous SDK can still be installed into the router using SDK version 2.0. However, the coding of an application version 1.0 may need to be re-factored in order for continued development with SDK version 2.0. Please see document SDK\_version\_1.0\_app_refactor.html in this directory for details.

## Documents 

- **README.html**
    - This README file.
- **Router\_Application\_Development_Guide.html**
    - The main document that describes application development.
- **Router\_APIs\_for_Applications.html**
    - The router config store API in the router.
- **GNU\_Make_README.html**
    - The Linux GNU make instructions for the SDK.

## Sample Application Directories 

- **app_template**
    - A skeleton template for the creation of a new application.
- **Boot1**
    - On bootup, this application will select test the connection of each sim in a dual sim modem and enable the best.
- **email**
    - Sends an email.
- **ftp_client**
    - Creates a file and uploads it to an FTP server.
- **ftp_server**
    - Creates an FTP server in the device. A USB memory device is used as the FTP directory.
- **gps_localhost**
    - Assuming the Cradlepoint device is configured to forward NMEA sentences to a localhost port, open the port as a server and receive the streaming GSP data.
- **gps_probe**
    - Probe the GPS hardware and log the results.
- **hello_world**
    - Outputs a 'Hello World!' log every 10 seconds. 
- **hspt**
    - Sets up a custom Hot Spot landing page.
- **list\_serial_ports**
    - Lists out the serial ports in the logs.
- **loglevel**
    - Changes the device log level.
- **modbus_poll**
    - Poll a single range of Modbus registers from an attached serial Modbus/RTU PLC or slave device.
- **modbus\_simple_bridge**
    - A basic Modbus/TCP to RTU bridge.
- **ping**
    - Ping an address and log the results.
- **power_gpio**
    - Query the 2x2 power connector GPIO.
- **python\_module_list**
    - This app will log the python version and modules in the device. It is intended to help with app development to show the python environment within the device.
- **send_alert**
    - Sends an alert to the ECM when the application is started and stopped.
- **send\_to_server**
    - Gets the '/status' from the device config store and send it to a test server.
- **serial_echo**
    - Waits for data to enter the serial port, then echo back out.
- **simple\_custom_dashboard**
    - Creates a simple dashboard using HTML and JS. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.
- **simple\_web_server**
    - A simple web server to receive messages. Note that any 'server function' requires the router firewall to be correctly changed to allow client access to the router.




## SDK Directories 

- **common**
    - Contains the cs.py file which should be copied into an  application folder. It is a wrapper for the TCP interface to the router config store.
- **config**
    - Contains the settings.mk file for Linux users that want to use GNU make for application development instead of python make.py.
- **tools**
    - Contains support files for the SDK. There is also a simple python syslog server that can be used during application development.

## Files 

- **make.py**
    - The main python tool used to build application packages and install, uninstall, start, stop, or purge from a locally connected device that is in DEV mode.
- **Makefile**
    - The Makefile for Linux users that want to use GNU make for application development instead of python make.py.
- **sdk_settings.ini**
    - This is the ini file that contains the settings used by python make.py.




