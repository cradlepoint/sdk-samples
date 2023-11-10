Installer_UI
============
**Provide a simple web interface for installers to configure WiFi and run speedtests.**

Usage
===================

The application runs a webserver on port 8000.  
The application adds a zone firewall forwarding from the Primary LAN Zone to the Router Zone to allow access to the UI.  
Installers can either connect to WiFi or connect to the LAN port and browse to http://192.168.0.1:8000  

![image](https://github.com/phate999/sdk-samples/assets/7169690/99041d46-2e71-4622-aff5-665ccbd77901)![image](https://github.com/phate999/sdk-samples/assets/7169690/f05a8ebc-b7b9-4737-9598-a72cc0a65685)![image](https://github.com/phate999/sdk-samples/assets/7169690/522841f2-1bc3-4e51-b75a-4634d6ebb12c)
![image](https://github.com/phate999/sdk-samples/assets/7169690/651443cb-636a-4ffa-bab2-2a739cbc25bf)

The UI displays the current WiFi SSID.  
The UI allows a user to configure the WiFi SSID and password.  User must enter the "Installer Password" to make changes.  
The "Installer Password" defaults to the serial number of the device and is stored in System > SDK Data where it can be
changed by admin users.  
Click "Save Settings" to save the WiFi configuration.  Requires installer password.  
Click "Run Speedtest" to perform an Ookla speedtest.  Requires installer password.  

Colors and branding can be customized:  
index.html can be found in /templates  
logo and CSS resources are in /static  
