Application Name
================
Installer_UI


Application Version
===================
0.1.0


NCOS Devices Supported
======================
ALL


Application Purpose
===================
Provide a simple web interface for installers to configure WiFi and run speedtests.

The application runs a webserver on port 8000.
The application adds a zone firewall forwarding from the Primary LAN Zone to the Router Zone to allow access to the UI.
Installers can either connect to WiFi or connect to the LAN port and browse to http://192.168.0.1:8000

The UI displays the current WiFi SSID.
The UI allows a user to configure the WiFi SSID and password.  User must enter the "Installer Password" to make changes.
The "Installer Password" defaults to the serial number of the device and is stored in System > SDK Data where it can be
changed by admin users.
When the submit button is pressed, user is shown a pop-up results window saying either:
"Success! Resetting WiFi..." or "Incorrect Password!"
