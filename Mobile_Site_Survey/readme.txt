Application Name
================
SNCF_MSS


Application Version
===================
2.5.3


External Requirements
=====================
- Modem(s) with cellular connectivity
- GPS antenna and location lock


Application Purpose
===================
This app is intended to perform rail testing of cellular networks but also works for testing stationary deployments.
It will run automatic tests collecting location (GPS), interface diagnostics (including cellular signal)

The app is configurable through a webUI running on port 8000.  Use NCM Remote Connect to 127.0.0.1 port 8000 HTTP.
Or locally, forward the Primary LAN Zone to the Router Zone with the Default Allow All policy.

* Execute Manual Survey - a button is provided at the top to start testing. Or delete the description field.
* Download Results - Opens a new tab with results files (CSV) available for download.
* Save Config - saves Mobile Site Survey configuration to router.

Survey Options:

* Enable Speedtests - Include Ookla TCP upload and download tests
* Speedtest Timer - Time between speedtests (in seconds)

* Enable Metrics - Gather cellular metrics
* Metrics Timer - Time between metrics (in seconds)

Note: New tests cannot start until all current interface tests complete.

* Write to .csv - Write test results to .csv file on router flash (Accessible via FTP server)
* Debug Logs - Additional debugging logs for application troubleshooting.

Send to Server
Powered by https://5g-ready.io
* Enable Send to Server - Application will send results to server using HTTP POST
* Include Full Interface Diagnostics - send all available diagnostics (not just signal)
* Include Application Logs - send testing logs (useful for troubleshooting)
* Server URL - The URL of the HTTP server to send the results to (e.g. https://5g-ready.io/injector)
* Server Token (optional): Bearer token for server authentication

Surveyors
If you have multiple routers that you would like to synchronize testing with the app will start them at the same time.
Be sure routers are reachable on port 8000.
* Enable Surveyors - Trigger remote routers applications to test at the same time
* Surveyors - Enter the IP Addresses of other routers, separated by commas.

---

By default the app will tests every 50 meters including speedtests and write results to a .csv file.

You can edit the default settings in settings.py

---

Changelog:

2.5.3:
Added "version" to CSV filename, logs, and send-to-server payload.
Added fields "cur_plmn", "tac", and "lac" to CSV and send-to-server payload.
Added 5g-ready status indicator to results.
