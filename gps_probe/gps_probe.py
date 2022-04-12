"""
Probe the GPS hardware and log the results.
"""
from csclient import EventingCSClient

cp = EventingCSClient("gps_probe")

gps_enabled = cp.get("/config/system/gps/enabled")

if not gps_enabled:
    cp.log("GPS Function is NOT Enabled")
else:
    cp.log("GPS Function is Enabled")
    gps_data = cp.get("/status/gps")
    cp.log(gps_data)
