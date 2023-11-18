Installer_UI
============

**Provide a simple web interface for installers to configure WiFi and run speedtests.**  

The application runs a tornado webserver on port 8000.  
The application adds a zone firewall forwarding from the Primary LAN Zone to the Router Zone to allow access to the UI.  
Installers can either connect to WiFi or connect to the LAN port and browse to http://192.168.0.1:8000  

![image](https://github.com/cradlepoint/sdk-samples/assets/7169690/f7a9aa2b-7648-42a3-a033-c8eafbba518c)![image](https://github.com/cradlepoint/sdk-samples/assets/7169690/3abb3d57-4fac-4f94-886a-9ac22cb36446)

The UI displays the current WiFi SSID.  
The UI allows a user to configure the WiFi SSID and password.  User must enter the "Installer Password" to make changes.  
The "Installer Password" defaults to the serial number of the device and is stored in System > SDK Data where it can be
changed by admin users.  

Customizable index.html
