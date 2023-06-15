![image](https://github.com/phate999/sdk-samples/assets/7169690/2586842b-d489-4963-97ce-e465fb0cf0ad)

Application Name
================
Mobile Site Survey


Application Version
===================
2.3.2


External Requirements
=====================
- Modem(s) with cellular connectivity  
- GPS antenna and location lock  


Application Purpose
===================
This app is intended to perform testing of cellular networks and connections.
It will run automatic tests collecting location (GPS), interface diagnostics (including cellular signal),
latency, and packet loss.

Create an NCM Remote Connect LAN Manager profile for "Mobile Site Survey" at 127.0.0.1 port **8000** HTTP.
Create an NCM Remote Connect LAN Manager profile for "Survey Results" at 127.0.0.1 port **8001** HTTP.

If accessing the UI locally, forward the PrimaryLAN Zone to the Router Zone with the Default Allow All policy.  

Buttons:

* Run Survey Now - a button is provided at the top to start testing.
* Download Results (Local Only - No Remote Connect) - List results files for download.
* Save Config - saves configuration to /config/system/sdk/appdata/

Survey Options:  

* Enabled (Automatically test at distance) - The app will run tests when the router has moved the distance defined.  
* Distance Between Tests (meters) - Set the distance for automatic testing.  

* Timed Tests - The app will run tests at the time interval defined.  
* Time Between Tests (seconds) - Set the time interval for automatic testing.  

Both distance and timed tests can be enabled.  
Note: New tests cannot start until all current interface tests complete.  

* Test ALL connected WAN interfaces (not just modems) - This will also test Ethernet and Wifi-as-WAN interfaces.  
* Run Speedtests - Include Ookla TCP upload and download tests (if disabled, app will ping 8.8.8.8 to measure latency).  
* Write to .csv - Write test results to .csv file on router flash (Accessible via FTP server).  
* Debug Logs - Additional debugging logs for application troubleshooting.  

Send to Server  
Powered by https://5g-ready.io  
* Enable Send to Server - Application will send results to server using HTTP POST.  
* Include Full Interface Diagnostics - send all available diagnostics (not just signal).  
* Include Application Logs - send testing logs (useful for troubleshooting).  
* Server URL - The URL of the HTTP server to send the results to (e.g. https://5g-ready.io/injector).  
* Server Token (optional): Bearer token for server authentication.  

Surveyors  
If you have multiple routers that you would like to synchronize testing with the app will start them at the same time.  
Be sure routers are reachable on port 8000.  
* Enable Surveyors - Trigger remote routers applications to test at the same time  
* Surveyors - Enter the IP Addresses of other routers, separated by commas.  

---

By default the app will tests every 50 meters including speedtests and write results to a .csv file.  

You can edit the default settings in settings.py  

The following fields are reported by default:  
'Time', 'Latitude', 'Longitude', 'Carrier', 'Cell ID', 'Service Display', 'Band', 'SCELL0', 'SCELL1', 'SCELL2', 'SCELL3', 'RSSI', 'SINR',
'RSRP', 'RSRQ', 'State', 'Download', 'Upload', 'Latency', 'Bytes Sent', 'Bytes Received', 'Results URL'
