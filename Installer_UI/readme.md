Installer_UI
============

**Provide a simple web interface for installers to configure WiFi and run speedtests.**  

The application runs a tornado webserver on port 8000.  
The application adds a zone firewall forwarding from the Primary LAN Zone to the Router Zone to allow access to the UI.  
Installers can either connect to WiFi or connect to the LAN port and browse to http://192.168.0.1:8000  

![image](https://github.com/user-attachments/assets/a0af6ae2-a9dd-46de-a294-10c8468cec8d)

![image](https://github.com/user-attachments/assets/a91d5828-e81e-47a1-a16b-e8c1240240d1)

![image](https://github.com/user-attachments/assets/2a74cdae-491c-42d6-9502-7436e3058d97)

* The UI displays the current WiFi SSID.  
* The UI allows a user to configure the WiFi SSID and password.  User must enter the "Installer Password" to make changes.  
* The "Signal Monitor" button takes you to the Cellular Signal Monitor page.  
* The "Run Speedtest" button runs an Ookla speedtest.  
* The "Installer Password" defaults to the serial number of the device and is stored in System > SDK Data where it can be
changed by admin users.  

Customizable index.html  
