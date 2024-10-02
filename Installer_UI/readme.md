Installer_UI
============

**Provide a simple web interface for installers to configure WiFi and run speedtests.**  

The application runs a tornado webserver on port 8000.  
The application adds a zone firewall forwarding from the Primary LAN Zone to the Router Zone to allow access to the UI.  
Installers can either connect to WiFi or connect to the LAN port and browse to http://192.168.0.1:8000  

![image](https://github.com/user-attachments/assets/cc0d39d2-d9cd-4586-ac87-6ac8595f001b)

![image](https://github.com/user-attachments/assets/e9e039c0-f002-4c93-bee4-28c61dafe50c)

![image](https://github.com/cradlepoint/sdk-samples/assets/7169690/3abb3d57-4fac-4f94-886a-9ac22cb36446)

* The UI displays the current WiFi SSID.  
* The UI allows a user to configure the WiFi SSID and password.  User must enter the "Installer Password" to make changes.  
* The "Signal Monitor" button takes you to the Cellular Signal Monitor page.  
* The "Run Speedtest" button runs an Ookla speedtest.  
* The "Installer Password" defaults to the serial number of the device and is stored in System > SDK Data where it can be
changed by admin users.  

Customizable index.html  
