Application Name
================
Mobile Site Survey


Application Version
===================
1.2


External Requirements
=====================
- Modem(s) with cellular connectivity
- GPS antenna and location lock


Application Purpose
===================
This app is intended to perform drive testing of cellular networks.

The app is configurable through a webUI running on port 8000.  Use remote connect to 127.0.0.1, or add a ZFW Forwarding
from LAN Zone to Router Zone.

By default the app will check for GPS lock and every 50 meters will collect modem diagnostics and run speedtests.
It will write results to a .csv file in flash memory.  And FTP server provides access to files.

Edit default settings in settings.py

Send to Server will HTTP POST the results in JSON body to the Server URL and supply the optional Server Token (Bearer)

If Write to CSV is enabled, a CSV file will be created in the routers flash storage named "Mobile Site Survey - ICCID {ICCID}.csv"

The following fields are reported tests.
'Time', 'Latitude', 'Longitude', 'Carrier', 'Cell ID', 'Service Display', 'Band', 'SCELL0', 'SCELL1', 'SCELL2', 'SCELL3', 'RSSI', 'SINR',
'RSRP', 'RSRQ', 'State', 'Download', 'Upload', 'Latency', 'Bytes Sent', 'Bytes Received', 'Results URL'
